"""Debt collection reminder preview + Mobile Sasa personalized bulk send."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from sales.models import Customer
from settings.store_settings_helpers import resolved_store_name

from .models import MessageOutbox, SmsTemplate
from .providers import get_sms_provider
from .templates_sms import (
    DEFAULT_DEBT_COLLECTION_TEMPLATE,
    customer_greeting_name,
    render_debt_collection_reminder,
)


class MessagingError(ValidationError):
    pass


def get_debt_reminder_template_body() -> str:
    row = SmsTemplate.objects.filter(key=SmsTemplate.KEY_DEBT_REMINDER).first()
    body = (row.body if row else '') or ''
    return body.strip() or DEFAULT_DEBT_COLLECTION_TEMPLATE


def save_debt_reminder_template(body: str, *, user=None) -> SmsTemplate:
    text = (body or '').strip()
    if not text:
        raise MessagingError({'body': 'Template cannot be empty.'})
    if len(text) > 600:
        raise MessagingError({'body': 'Keep the template under 600 characters.'})
    row, _ = SmsTemplate.objects.update_or_create(
        key=SmsTemplate.KEY_DEBT_REMINDER,
        defaults={'body': text, 'updated_by': user},
    )
    return row


def _owed(customer: Customer) -> Decimal:
    bal = customer.wallet_balance or Decimal('0')
    return abs(bal) if bal < 0 else Decimal('0')


def build_debt_reminder_preview(
    *,
    template: str | None = None,
    customer_ids: list[int] | None = None,
) -> dict:
    body_template = (template or '').strip() or get_debt_reminder_template_body()
    store_name = resolved_store_name()
    recipients = []
    skipped_no_phone = 0
    total_debt = Decimal('0')

    qs = Customer.objects.filter(wallet_balance__lt=0).order_by('wallet_balance', 'name')
    if customer_ids is not None:
        qs = qs.filter(pk__in=customer_ids)

    for customer in qs:
        amount = _owed(customer)
        phone = (customer.phone or '').strip()
        if not phone:
            skipped_no_phone += 1
            continue
        name = customer_greeting_name(customer)
        message = render_debt_collection_reminder(
            template=body_template,
            name=name,
            amount=amount,
            store_name=store_name,
        )
        recipients.append({
            'customer_id': customer.pk,
            'name': customer.name,
            'greeting_name': name,
            'phone': phone,
            'amount': str(amount.quantize(Decimal('0.01'))),
            'message': message,
            'message_chars': len(message),
        })
        total_debt += amount

    return {
        'template': body_template,
        'store_name': store_name,
        'placeholders': ['{name}', '{amount}', '{store_name}'],
        'hint': (
            'Suggested cadence: review every Monday, verify the list, then send. '
            '{name} uses the duka name when set, otherwise the owner first name.'
        ),
        'count': len(recipients),
        'skipped_no_phone': skipped_no_phone,
        'total_debt': str(total_debt.quantize(Decimal('0.01'))),
        'recipients': recipients,
    }


@transaction.atomic
def send_debt_reminders(
    *,
    created_by=None,
    template: str | None = None,
    customer_ids: list[int] | None = None,
    save_template: bool = False,
) -> dict:
    """
    Personalized bulk via Mobile Sasa (different name/amount per phone).
    Creates MessageOutbox rows for audit; provider returns one bulkId.
    """
    preview = build_debt_reminder_preview(template=template, customer_ids=customer_ids)
    recipients = preview['recipients']
    if not recipients:
        raise MessagingError({'recipients': 'No debtors with a phone number to remind.'})

    if save_template and template is not None:
        save_debt_reminder_template(template, user=created_by)

    body_template = preview['template']
    provider_messages = [
        {'phone': r['phone'], 'message': r['message']}
        for r in recipients
    ]

    outbox_ids = []
    for r in recipients:
        msg = MessageOutbox.objects.create(
            to_phone=r['phone'],
            body=r['message'],
            template_key=MessageOutbox.TEMPLATE_DEBT_REMINDER,
            customer_id=r['customer_id'],
            created_by=created_by,
            status=MessageOutbox.STATUS_PENDING,
        )
        outbox_ids.append(msg.pk)

    provider = get_sms_provider()
    result = provider.send_bulk_personalized(messages=provider_messages)
    now = timezone.now()
    provider_name = getattr(provider, 'name', '') or ''

    if result.ok:
        MessageOutbox.objects.filter(pk__in=outbox_ids).update(
            status=MessageOutbox.STATUS_SENT,
            provider=provider_name,
            provider_ref=result.provider_ref,
            sent_at=now,
            error='',
        )
    else:
        MessageOutbox.objects.filter(pk__in=outbox_ids).update(
            status=MessageOutbox.STATUS_FAILED,
            provider=provider_name,
            error=result.error,
        )
        raise MessagingError({'sms': result.error or 'SMS provider rejected the bulk send.'})

    return {
        'queued': len(recipients),
        'bulk_id': result.provider_ref,
        'provider': provider_name,
        'template': body_template,
        'total_debt': preview['total_debt'],
        'ids': outbox_ids,
    }


@transaction.atomic
def queue_debt_reminders(*, created_by=None, limit: int = 50) -> list[MessageOutbox]:
    """Legacy one-by-one path (kept for older clients / tests). Prefer send_debt_reminders."""
    debtors = (
        Customer.objects.filter(wallet_balance__lt=0)
        .order_by('wallet_balance')[:limit]
    )
    queued = []
    provider = get_sms_provider()
    template = get_debt_reminder_template_body()
    store_name = resolved_store_name()
    for customer in debtors:
        phone = (customer.phone or '').strip()
        if not phone:
            continue
        amount = _owed(customer)
        body = render_debt_collection_reminder(
            template=template,
            name=customer_greeting_name(customer),
            amount=amount,
            store_name=store_name,
        )
        msg = MessageOutbox.objects.create(
            to_phone=phone,
            body=body,
            template_key=MessageOutbox.TEMPLATE_DEBT_REMINDER,
            customer=customer,
            created_by=created_by,
        )
        result = provider.send(to=phone, body=body)
        msg.provider = getattr(provider, 'name', '') or ''
        if result.ok:
            msg.status = MessageOutbox.STATUS_SENT
            msg.provider_ref = result.provider_ref
            msg.sent_at = timezone.now()
        else:
            msg.status = MessageOutbox.STATUS_FAILED
            msg.error = result.error
        msg.save()
        queued.append(msg)
    return queued


def owed_amount(customer: Customer) -> Decimal:
    bal = customer.wallet_balance or Decimal('0')
    return abs(bal) if bal < 0 else Decimal('0')
