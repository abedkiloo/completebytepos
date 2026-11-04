"""
SMS template admin APIs and debt reminder preview/send.

Public entry points:
    - ``list_sms_templates`` / ``save_sms_template`` / ``reset_sms_template``
    - ``build_debt_reminder_preview`` / ``send_debt_reminders`` / ``queue_debt_reminders``
    - ``owed_amount`` — helper for debtor balance display

Side effects: ``send_*`` creates ``MessageOutbox`` rows and calls SMS providers.
Debt preview scans customers with ``wallet_balance < 0`` (optional id filter).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from sales.models import Customer
from settings.store_settings_helpers import resolved_store_name

from .models import MessageOutbox, SmsTemplate
from .providers import get_sms_provider
from .template_catalog import (
    all_template_specs,
    get_spec,
    get_template_body,
    is_customized,
)
from .templates_sms import (
    apply_sms_placeholders,
    customer_greeting_name,
    render_debt_collection_reminder,
)


class MessagingError(ValidationError):
    """Template, recipient, or provider failure surfaced to API callers."""


# Avoid circular import — preview helper lives next to catalog usage below.
def _preview_body(spec, body: str) -> str:
    return apply_sms_placeholders(body, **spec.sample)


def serialize_template(key: str) -> dict:
    """
    Build API payload for one SMS template key.

    Args:
        key: Catalog key (e.g. ``debt_reminder``).

    Returns:
        Dict with label, body, defaults, placeholders, preview, customization flags.

    Raises:
        MessagingError: Unknown key.
    """
    spec = get_spec(key)
    if spec is None:
        raise MessagingError({'key': f'Unknown template: {key}'})
    body = get_template_body(key)
    row = SmsTemplate.objects.filter(key=key).first()
    return {
        'key': spec.key,
        'label': spec.label,
        'description': spec.description,
        'category': spec.category,
        'body': body,
        'default_body': spec.default_body,
        'placeholders': [f'{{{p}}}' for p in spec.placeholders],
        'sample_preview': _preview_body(spec, body),
        'is_customized': is_customized(key),
        'updated_at': row.updated_at if row else None,
        'updated_by': (
            getattr(row.updated_by, 'username', None) if row and row.updated_by_id else None
        ),
    }


def list_sms_templates() -> list[dict]:
    """Return serialized metadata for every catalog template key."""
    return [serialize_template(spec.key) for spec in all_template_specs()]


def save_sms_template(key: str, body: str, *, user=None) -> dict:
    """
    Upsert customized template body for a catalog key.

    Args:
        key: Known template key.
        body: Non-empty text, max 600 characters after strip.
        user: Stored on ``updated_by``.

    Returns:
        Fresh ``serialize_template`` dict.

    Raises:
        MessagingError: Unknown key, empty body, or over length limit.

    Side effects:
        Creates/updates ``SmsTemplate`` row.
    """
    spec = get_spec(key)
    if spec is None:
        raise MessagingError({'key': f'Unknown template: {key}'})
    text = (body or '').strip()
    if not text:
        raise MessagingError({'body': 'Template cannot be empty.'})
    if len(text) > 600:
        raise MessagingError({'body': 'Keep the template under 600 characters.'})
    SmsTemplate.objects.update_or_create(
        key=key,
        defaults={'body': text, 'updated_by': user},
    )
    return serialize_template(key)


def reset_sms_template(key: str, *, user=None) -> dict:
    """
    Delete customization so catalog default body applies again.

    Args:
        key: Known template key.
        user: Accepted for API symmetry; not persisted on delete.

    Returns:
        ``serialize_template`` using default body.

    Raises:
        MessagingError: Unknown key.

    Side effects:
        Deletes ``SmsTemplate`` row when present.
    """
    spec = get_spec(key)
    if spec is None:
        raise MessagingError({'key': f'Unknown template: {key}'})
    SmsTemplate.objects.filter(key=key).delete()
    # Optionally store default explicitly so updated_by is tracked — prefer delete → default.
    return serialize_template(key)


def get_debt_reminder_template_body() -> str:
    """Return effective debt reminder body (DB override or catalog default)."""
    return get_template_body(SmsTemplate.KEY_DEBT_REMINDER)


def save_debt_reminder_template(body: str, *, user=None) -> SmsTemplate:
    """Persist debt reminder template and return the ``SmsTemplate`` row."""
    save_sms_template(SmsTemplate.KEY_DEBT_REMINDER, body, user=user)
    return SmsTemplate.objects.get(key=SmsTemplate.KEY_DEBT_REMINDER)


def _owed(customer: Customer) -> Decimal:
    bal = customer.wallet_balance or Decimal('0')
    return abs(bal) if bal < 0 else Decimal('0')


def build_debt_reminder_preview(
    *,
    template: str | None = None,
    customer_ids: list[int] | None = None,
) -> dict:
    """
    Preview personalized debt SMS for debtors with phone numbers.

    Args:
        template: Optional override body; defaults to stored debt reminder template.
        customer_ids: When set, restrict to these customer pks; else all debtors.

    Returns:
        Dict with template, counts, ``total_debt``, and per-recipient messages.
        Skips customers without phone (`skipped_no_phone` counter).

    Side effects:
        Read-only; no outbox rows created.
    """
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
    Send bulk personalized debt reminders via provider bulk API.

    Args:
        created_by: User stored on outbox rows.
        template: Optional body override for this send.
        customer_ids: Optional subset; same rules as preview.
        save_template: When True and ``template`` provided, persist before send.

    Returns:
        Dict with ``queued`` count, provider refs, template snapshot, outbox ids.

    Raises:
        MessagingError: No eligible recipients or provider bulk failure.

    Side effects:
        Creates pending outbox rows then bulk-updates to sent/failed.
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
    """
    Send debt reminders sequentially for the worst balances (legacy path).

    Args:
        created_by: User on outbox rows.
        limit: Max debtors to consider (ordered by most negative balance first).

    Returns:
        List of outbox rows actually sent or marked failed (skips no-phone).

    Side effects:
        One provider ``send`` per customer; immediate status update per row.
    """
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
    """Return absolute debt from negative ``wallet_balance``, else ``0.00``."""
    bal = customer.wallet_balance or Decimal('0')
    return abs(bal) if bal < 0 else Decimal('0')


def get_customer_week_template_body() -> str:
    return get_template_body(SmsTemplate.KEY_CUSTOMER_WEEK)


def build_customer_week_preview(**kwargs):
    from messaging.customer_blast import build_customer_week_preview as _build

    return _build(**kwargs)


def send_customer_week_promos(**kwargs):
    from messaging.customer_blast import send_customer_week_promos as _send

    return _send(**kwargs)
