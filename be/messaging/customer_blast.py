"""
Manual SMS to registered customers — any catalog template, all or one.

Transactional templates (sale/invoice) can still be previewed/sent; missing
sale-specific fields render empty so operators can soft-edit the body first.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from payments.config import get_brand_blurb
from sales.models import Customer
from settings.store_settings_helpers import resolved_store_name
from utils.phone import PhoneNumberError, normalize_phone_number

from .models import MessageOutbox, SmsTemplate
from .providers import get_sms_provider
from .template_catalog import get_spec, get_template_body
from .templates_sms import (
    apply_sms_placeholders,
    customer_greeting_name,
    format_balance_note,
    sms_cap_name,
    _money,
)


class BlastError(Exception):
    """Raised with a DRF-style detail dict."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(str(detail))


def _owed_amount(customer: Customer):
    from decimal import Decimal

    bal = customer.wallet_balance or Decimal('0')
    return abs(bal) if bal < 0 else Decimal('0')


def _save_sms_template(key: str, body: str, *, user=None):
    from .services import save_sms_template

    return save_sms_template(key, body, user=user)


def usable_customer_phone(raw) -> str | None:
    """Return normalized MSISDN when the number is valid; else None."""
    try:
        phone = normalize_phone_number(raw, required=True)
    except PhoneNumberError:
        return None
    return phone or None


def _offer_clause(offer: str | None) -> str:
    text = str(offer or '').strip()
    if text and not text.endswith((' ', '\n')):
        text = f'{text} '
    return text


def placeholder_values_for_customer(
    customer: Customer,
    *,
    offer: str | None = None,
    store_name: str | None = None,
) -> dict[str, str]:
    greeting = customer_greeting_name(customer)
    store = store_name or resolved_store_name()
    owed = _owed_amount(customer)
    balance_note = format_balance_note(owed)
    offer_text = _offer_clause(offer)
    return {
        'name': greeting,
        'first_name': greeting,
        'customer_name': greeting,
        'store_name': sms_cap_name(store, fallback='us', first_word_only=False),
        'offer': offer_text,
        'amount': _money(owed),
        'balance': _money(owed),
        'balance_note': balance_note,
        'debt_bit': balance_note,
        'payment_ref': '',
        'sale_number': '',
        'items': '',
        'total': _money(0),
        'paid': _money(0),
        'brand_blurb': get_brand_blurb(),
        'invoice_no': '',
        'link': '',
    }


def render_blast_sms(
    *,
    template_key: str,
    customer: Customer,
    template: str | None = None,
    offer: str | None = None,
    store_name: str | None = None,
) -> str:
    spec = get_spec(template_key)
    if spec is None:
        raise BlastError({'template_key': f'Unknown template: {template_key}'})
    body = (template or '').strip() or get_template_body(template_key)
    values = placeholder_values_for_customer(
        customer, offer=offer, store_name=store_name
    )
    return apply_sms_placeholders(body, **values)


def _blast_queryset(
    *,
    template_key: str,
    scope: str,
    customer_id: int | None = None,
    customer_ids: list[int] | None = None,
):
    qs = Customer.objects.filter(is_active=True).order_by('name')
    # Debt collection SMS only targets customers who currently owe.
    if template_key == SmsTemplate.KEY_DEBT_REMINDER:
        qs = qs.filter(wallet_balance__lt=0)
    scope = (scope or 'all').strip().lower()
    if scope == 'one':
        if not customer_id:
            raise BlastError({'customer_id': 'Pick one customer to message.'})
        qs = qs.filter(pk=int(customer_id))
    elif customer_ids is not None:
        qs = qs.filter(pk__in=[int(x) for x in customer_ids])
    return qs, scope


def build_customer_blast_preview(
    *,
    template_key: str,
    template: str | None = None,
    offer: str | None = None,
    scope: str = 'all',
    customer_id: int | None = None,
    customer_ids: list[int] | None = None,
) -> dict:
    spec = get_spec(template_key)
    if spec is None:
        raise BlastError({'template_key': f'Unknown template: {template_key}'})

    body_template = (template or '').strip() or get_template_body(template_key)
    offer_text = '' if offer is None else str(offer)
    store_name = resolved_store_name()
    qs, scope_norm = _blast_queryset(
        template_key=template_key,
        scope=scope,
        customer_id=customer_id,
        customer_ids=customer_ids,
    )
    debt_only = template_key == SmsTemplate.KEY_DEBT_REMINDER

    recipients = []
    skipped_no_phone = 0
    skipped_invalid_phone = 0

    for customer in qs:
        raw = (customer.phone or '').strip()
        if not raw:
            skipped_no_phone += 1
            continue
        phone = usable_customer_phone(raw)
        if not phone:
            skipped_invalid_phone += 1
            continue
        message = render_blast_sms(
            template_key=template_key,
            customer=customer,
            template=body_template,
            offer=offer_text,
            store_name=store_name,
        )
        recipients.append({
            'customer_id': customer.pk,
            'name': customer.name,
            'greeting_name': customer_greeting_name(customer),
            'phone': phone,
            'phone_raw': raw,
            'message': message,
            'message_chars': len(message),
            'amount': str(_owed_amount(customer)),
        })

    if debt_only:
        hint = (
            'Debt collection only includes customers who currently owe. '
            'Send to all debtors with a valid phone, or pick one. '
            '{name} uses the short greeting name; {amount} is their balance.'
        )
    else:
        hint = (
            'Send to all registered customers with a valid phone, or pick one. '
            'Only correct Kenyan mobiles are included. '
            '{name} / {first_name} use the short greeting name.'
        )

    return {
        'template_key': template_key,
        'template_label': spec.label,
        'category': spec.category,
        'template': body_template,
        'offer': offer_text,
        'store_name': store_name,
        'scope': scope_norm,
        'debt_only': debt_only,
        'placeholders': [f'{{{p}}}' for p in spec.placeholders],
        'hint': hint,
        'count': len(recipients),
        'skipped_no_phone': skipped_no_phone,
        'skipped_invalid_phone': skipped_invalid_phone,
        'recipients': recipients,
    }


@transaction.atomic
def send_customer_blast(
    *,
    template_key: str,
    created_by=None,
    template: str | None = None,
    offer: str | None = None,
    scope: str = 'all',
    customer_id: int | None = None,
    customer_ids: list[int] | None = None,
    save_template: bool = False,
) -> dict:
    preview = build_customer_blast_preview(
        template_key=template_key,
        template=template,
        offer=offer,
        scope=scope,
        customer_id=customer_id,
        customer_ids=customer_ids,
    )
    recipients = preview['recipients']
    if not recipients:
        raise BlastError(
            {
                'recipients': (
                    'No customers with a valid phone number to message.'
                )
            }
        )

    if save_template and template is not None:
        _save_sms_template(template_key, template, user=created_by)

    provider_messages = [
        {'phone': r['phone'], 'message': r['message']}
        for r in recipients
    ]
    outbox_ids = []
    for r in recipients:
        msg = MessageOutbox.objects.create(
            to_phone=r['phone'],
            body=r['message'],
            template_key=template_key,
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
        raise BlastError(
            {'sms': result.error or 'SMS provider rejected the bulk send.'}
        )

    return {
        'queued': len(recipients),
        'bulk_id': result.provider_ref,
        'provider': provider_name,
        'template_key': template_key,
        'template': preview['template'],
        'offer': preview['offer'],
        'scope': preview['scope'],
        'ids': outbox_ids,
    }


# Keep Customer Week helpers thin wrappers for older callers / tests.
def build_customer_week_preview(**kwargs):
    kwargs.setdefault('template_key', SmsTemplate.KEY_CUSTOMER_WEEK)
    kwargs.setdefault('scope', 'all')
    return build_customer_blast_preview(**kwargs)


def send_customer_week_promos(**kwargs):
    kwargs.setdefault('template_key', SmsTemplate.KEY_CUSTOMER_WEEK)
    kwargs.setdefault('scope', 'all')
    return send_customer_blast(**kwargs)
