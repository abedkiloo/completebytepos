"""
PaymentIntent lifecycle, Daraja STK, callbacks, and invoice SMS.

Public entry points:
    - ``create_intent`` / ``initiate_stk`` — start STK push
    - ``process_callback`` / ``reconcile_query`` — Daraja result ingestion
    - ``mark_paid`` / ``mark_failed`` — terminal transitions
    - ``queue_invoice_sms`` / ``dispatch_message`` — outbox + provider send

Side effects: updates intent rows; paid path queues ``MessageOutbox`` and sends SMS.
Callbacks are idempotent when already paid with ``callback_processed``.
"""

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
    """Illegal intent transition, phone/amount validation, or Daraja/callback errors."""


def normalize_phone(phone: str) -> str:
    """
    Normalize a Kenyan MSISDN for Daraja STK.

    Args:
        phone: Raw phone string from client.

    Returns:
        Normalized number accepted by ``utils.phone``.

    Raises:
        PaymentTransitionError: Invalid or missing phone.
    """
    from utils.phone import PhoneNumberError, normalize_phone_number

    try:
        return normalize_phone_number(phone, required=True)
    except PhoneNumberError as exc:
        raise PaymentTransitionError({'phone': str(exc)})


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
    """
    Create a payment intent in ``STATUS_CREATED``.

    Args:
        amount: Positive money amount (2 dp after coercion).
        phone: Customer MSISDN; normalized on save path.
        purpose: One of ``PaymentIntent.PURPOSE_*``; defaults to ``other``.
        customer: Optional linked ``Customer``.
        customer_name: Snapshot name; defaults to ``customer.name`` when blank.
        created_by: Staff user who initiated the intent.
        client_uuid: Optional unique idempotency key for mobile (DB unique).

    Returns:
        Saved ``PaymentIntent`` with generated token/invoice when applicable.

    Raises:
        PaymentTransitionError: Amount ≤ 0 or invalid phone.

    Side effects:
        Inserts intent row only; does not call Daraja until ``initiate_stk``.
    """
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
    """
    Prompt M-Pesa STK for an intent via Daraja.

    Args:
        intent: Must be ``created`` or ``failed``; ``prompted`` returns unchanged.

    Returns:
        Intent in ``STATUS_PROMPTED`` with checkout/merchant request IDs set.

    Raises:
        PaymentTransitionError: Illegal status for STK (e.g. already paid).

    Side effects:
        External Daraja API call; stores STK identifiers on the intent.
    """
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
    """
    Mark an intent paid and queue invoice SMS once.

    Args:
        intent: Intent to close as paid.
        mpesa_receipt: M-Pesa receipt number (may be empty string).
        payload: Optional raw callback JSON stored on the intent.

    Returns:
        Intent in ``STATUS_PAID``; no-op when already paid.

    Side effects:
        Sets ``callback_processed``; calls ``queue_invoice_sms`` on first paid transition.
    """
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
    """
    Mark an intent failed with a human-readable reason.

    Args:
        intent: Target intent; other terminal states (except failed) are left unchanged.
        reason: Failure description stored on ``failure_reason``.
        payload: Optional callback JSON.

    Returns:
        Intent in ``STATUS_FAILED`` or unchanged when already terminal (non-failed).

    Side effects:
        Sets ``callback_processed=True``.
    """
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
    Idempotent Daraja STK callback handler.

    Expected shape (sandbox/production simplified):
    ``Body.stkCallback.CheckoutRequestID``, ``ResultCode``, and on success
    ``CallbackMetadata.Item`` with ``MpesaReceiptNumber``.

    Args:
        payload: Raw POST JSON from Daraja.

    Returns:
        Updated ``PaymentIntent``, or early return when already paid/processed.

    Raises:
        PaymentTransitionError: Missing checkout ID or unknown intent.

    Side effects:
        Delegates to ``mark_paid`` or ``mark_failed`` (SMS on paid).
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
    """
    Poll Daraja for STK status when callbacks are delayed.

    Args:
        intent: Must have ``checkout_request_id``; paid intents return unchanged.

    Returns:
        Intent after paid/failed update, or unchanged when still processing
        (Daraja codes ``4999`` / ``1037``).

    Raises:
        PaymentTransitionError: No checkout ID to query.

    Side effects:
        External query API; may mark paid/failed like callback.
    """
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
    """
    Enqueue and immediately dispatch invoice SMS for a paid intent.

    Args:
        intent: Paid intent with phone and ``public_token`` for link rendering.

    Returns:
        Existing latest message when ``sms_queued`` already True; else new outbox row.

    Side effects:
        Creates ``MessageOutbox``; sets ``sms_queued``; calls ``dispatch_message``.
    """
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
    """
    Send one outbox row through the configured SMS provider.

    Args:
        msg: Pending or retry candidate with ``to_phone`` and ``body``.

    Returns:
        Same row updated to ``sent`` or ``failed`` with provider metadata.

    Side effects:
        External SMS API; persists status, ref, error, and ``sent_at``.
    """
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
