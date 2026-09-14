"""PaymentIntent state machine + Daraja STK + SMS on paid."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from messaging.models import MessageOutbox
from messaging.providers import get_sms_provider
from messaging.templates_sms import render_invoice_sms

from .daraja import get_daraja_client
from .models import PaymentIntent


class PaymentTransitionError(ValidationError):
    """Illegal intent transition or Daraja precondition failure."""


def normalize_phone(phone: str) -> str:
    digits = ''.join(c for c in (phone or '') if c.isdigit())
    if digits.startswith('0') and len(digits) == 10:
        digits = '254' + digits[1:]
    if digits.startswith('254') and len(digits) == 12:
        return digits
    raise PaymentTransitionError({'phone': 'Use a valid KE MSISDN (07… or 254…).'})


@transaction.atomic
def create_intent(
    *,
    amount,
    phone: str,
    purpose: str = PaymentIntent.PURPOSE_OTHER,
    customer=None,
    customer_name: str = '',
    created_by=None,
    client_uuid=None,
) -> PaymentIntent:
    amount = Decimal(str(amount))
    if amount <= 0:
        raise PaymentTransitionError({'amount': 'Amount must be greater than zero.'})
    msisdn = normalize_phone(phone)
    intent = PaymentIntent(
        amount=amount,
        phone=msisdn,
        purpose=purpose or PaymentIntent.PURPOSE_OTHER,
        customer=customer,
        customer_name=customer_name or (customer.name if customer else ''),
        created_by=created_by,
        client_uuid=client_uuid,
    )
    intent.save()
    return intent


@transaction.atomic
def initiate_stk(intent: PaymentIntent) -> PaymentIntent:
    if intent.status not in (PaymentIntent.STATUS_CREATED, PaymentIntent.STATUS_FAILED):
        if intent.status == PaymentIntent.STATUS_PROMPTED:
            return intent
        raise PaymentTransitionError({
            'status': f'Cannot STK from status {intent.status}.',
        })
    client = get_daraja_client()
    result = client.initiate_stk(
        phone=intent.phone,
        amount=str(int(intent.amount)) if intent.amount == intent.amount.to_integral_value()
        else str(intent.amount),
        account_reference=intent.invoice_number[:12],
        transaction_desc=f'Pay {intent.invoice_number}',
    )
    intent.checkout_request_id = result.checkout_request_id
    intent.merchant_request_id = result.merchant_request_id
    intent.status = PaymentIntent.STATUS_PROMPTED
    intent.prompted_at = timezone.now()
    intent.failure_reason = ''
    intent.save(update_fields=[
        'checkout_request_id', 'merchant_request_id', 'status',
        'prompted_at', 'failure_reason', 'updated_at',
    ])
    return intent


@transaction.atomic
def mark_paid(
    intent: PaymentIntent,
    *,
    mpesa_receipt: str,
    payload=None,
) -> PaymentIntent:
    if intent.status == PaymentIntent.STATUS_PAID:
        return intent
    intent.status = PaymentIntent.STATUS_PAID
    intent.mpesa_receipt = mpesa_receipt or intent.mpesa_receipt
    intent.paid_at = timezone.now()
    intent.callback_processed = True
    if payload is not None:
        intent.callback_payload = payload
    intent.save(update_fields=[
        'status', 'mpesa_receipt', 'paid_at', 'callback_processed',
        'callback_payload', 'updated_at',
    ])
    queue_invoice_sms(intent)
    return intent


@transaction.atomic
def mark_failed(intent: PaymentIntent, *, reason: str, payload=None) -> PaymentIntent:
    if intent.is_terminal and intent.status != PaymentIntent.STATUS_FAILED:
        return intent
    intent.status = PaymentIntent.STATUS_FAILED
    intent.failure_reason = reason or 'Failed'
    intent.callback_processed = True
    if payload is not None:
        intent.callback_payload = payload
    intent.save(update_fields=[
        'status', 'failure_reason', 'callback_processed',
        'callback_payload', 'updated_at',
    ])
    return intent


@transaction.atomic
def process_callback(payload: dict) -> PaymentIntent | None:
    """
    Idempotent Daraja callback handler.
    Expected shape (simplified sandbox):
      Body.stkCallback.CheckoutRequestID, ResultCode, CallbackMetadata.Item
    """
    body = payload.get('Body') or payload
    stk = body.get('stkCallback') or body
    checkout = stk.get('CheckoutRequestID') or stk.get('checkout_request_id')
    if not checkout:
        raise PaymentTransitionError({'callback': 'Missing CheckoutRequestID.'})
    try:
        intent = PaymentIntent.objects.select_for_update().get(
            checkout_request_id=checkout,
        )
    except PaymentIntent.DoesNotExist as exc:
        raise PaymentTransitionError({
            'callback': 'Unknown CheckoutRequestID.',
        }) from exc

    if intent.callback_processed and intent.status == PaymentIntent.STATUS_PAID:
        return intent

    result_code = str(stk.get('ResultCode', stk.get('result_code', '')))
    if result_code == '0':
        receipt = ''
        meta = (stk.get('CallbackMetadata') or {}).get('Item') or []
        for item in meta:
            if item.get('Name') == 'MpesaReceiptNumber':
                receipt = str(item.get('Value') or '')
        return mark_paid(intent, mpesa_receipt=receipt, payload=payload)

    desc = stk.get('ResultDesc') or stk.get('result_desc') or 'STK failed'
    return mark_failed(intent, reason=str(desc), payload=payload)


@transaction.atomic
def reconcile_query(intent: PaymentIntent) -> PaymentIntent:
    if not intent.checkout_request_id:
        raise PaymentTransitionError({'status': 'No STK checkout to query.'})
    if intent.status == PaymentIntent.STATUS_PAID:
        return intent
    result = get_daraja_client().query_stk(intent.checkout_request_id)
    if result.result_code == '0':
        return mark_paid(intent, mpesa_receipt=result.mpesa_receipt)
    if result.result_code in ('4999', '1037'):  # still processing
        return intent
    return mark_failed(intent, reason=result.result_desc)


def queue_invoice_sms(intent: PaymentIntent) -> MessageOutbox | None:
    if intent.sms_queued:
        return intent.messages.order_by('-id').first()
    body = render_invoice_sms(
        customer_name=intent.customer_name,
        invoice_no=intent.invoice_number,
        amount=intent.amount,
        public_token=intent.public_token,
    )
    msg = MessageOutbox.objects.create(
        to_phone=intent.phone,
        body=body,
        template_key=MessageOutbox.TEMPLATE_INVOICE,
        payment_intent=intent,
        customer=intent.customer,
        created_by=intent.created_by,
    )
    intent.sms_queued = True
    intent.save(update_fields=['sms_queued', 'updated_at'])
    dispatch_message(msg)
    return msg


def dispatch_message(msg: MessageOutbox) -> MessageOutbox:
    provider = get_sms_provider()
    result = provider.send(to=msg.to_phone, body=msg.body)
    msg.provider = getattr(provider, 'name', '') or ''
    if result.ok:
        msg.status = MessageOutbox.STATUS_SENT
        msg.provider_ref = result.provider_ref
        msg.sent_at = timezone.now()
        msg.error = ''
    else:
        msg.status = MessageOutbox.STATUS_FAILED
        msg.error = result.error
    msg.save()
    return msg
