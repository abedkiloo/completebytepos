"""SMS template rendering — defaults + DB overrides via template_catalog."""

from __future__ import annotations

import re
from decimal import Decimal

from payments.config import PUBLIC_INVOICE_BASE_URL, get_brand_blurb

from .models import SmsTemplate
from .template_catalog import get_template_body

# Backward-compatible alias used by older tests / callers.
INVOICE_TEMPLATE = get_template_body(SmsTemplate.KEY_INVOICE)


def _money(amount) -> str:
    try:
        value = Decimal(str(amount or 0)).quantize(Decimal('0.01'))
    except Exception:
        value = Decimal('0.00')
    text = f'{value:f}'
    if text.endswith('.00'):
        return text[:-3]
    return text.rstrip('0').rstrip('.') if '.' in text else text


def sms_cap_name(
    value: str | None,
    *,
    fallback: str = '',
    first_word_only: bool = True,
) -> str:
    """
    Clean a person or shop name for SMS.

    - Drop everything from the first ``[`` onward (internal tags).
    - For greetings (``first_word_only=True``): keep only the first word, e.g.
      ``mwangi wa jogoo rd zip`` → ``Mwangi``,
      ``Sunrise Duka [Route 3]`` → ``Sunrise``.
    - For store names (``first_word_only=False``): keep all remaining words and
      capitalize each first letter.
    """
    text = str(value or '').strip()
    if not text:
        return fallback
    bracket = text.find('[')
    if bracket >= 0:
        text = text[:bracket].strip()
    if not text:
        return fallback
    words = [w for w in text.split() if w]
    if not words:
        return fallback
    if first_word_only:
        words = words[:1]
    return ' '.join(w[:1].upper() + w[1:] for w in words)


def apply_sms_placeholders(template: str, **values) -> str:
    """Replace {key} tokens without str.format (avoids brace crashes)."""
    body = template or ''
    for key, value in values.items():
        body = body.replace('{' + key + '}', str(value))
    return body


def sale_number_token(sale_number: str) -> str:
    """
    Number / id part of a sale reference for SMS.

    SALE-0001 → 0001, S-ABC12 → ABC12, HOLD-042 → 042
    """
    raw = str(sale_number or '').strip()
    if not raw:
        return ''
    if '-' in raw or '_' in raw:
        part = re.split(r'[-_]', raw)[-1].strip()
        return part or raw
    match = re.search(r'([0-9][0-9A-Za-z]*)$', raw)
    if match:
        return match.group(1)
    return raw


def format_sale_number_for_sms(
    sale_number: str,
    *,
    short: bool | None = None,
    prefix: str | None = None,
) -> str:
    """
    Format sale ref for customer SMS.

    When short mode is on (default): SALE-0001 → S-0001 (prefix configurable).
    When off: returns the full sale_number unchanged.
    """
    raw = str(sale_number or '').strip() or 'sale'
    if short is None or prefix is None:
        from sales.module_settings import (
            sales_sms_sale_number_prefix,
            sales_sms_short_sale_number,
        )

        if short is None:
            short = sales_sms_short_sale_number()
        if prefix is None:
            prefix = sales_sms_sale_number_prefix()
    if not short:
        return raw
    token = sale_number_token(raw)
    if not token:
        return raw
    return f'{prefix}{token}'


def _item_display_name(item, *, name_max: int = 18) -> str:
    product = getattr(item, 'product', None)
    name = str(getattr(product, 'name', None) or 'Item').strip() or 'Item'
    size = getattr(item, 'size', None) or getattr(getattr(item, 'variant', None), 'size', None)
    color = getattr(item, 'color', None) or getattr(getattr(item, 'variant', None), 'color', None)
    bits = []
    if size is not None and getattr(size, 'name', None):
        bits.append(str(size.name))
    if color is not None and getattr(color, 'name', None):
        bits.append(str(color.name))
    if bits:
        name = f'{name} ({"/".join(bits)})'
    if len(name) > name_max:
        return name[: name_max - 1] + '…'
    return name


def _item_unit_price(item) -> Decimal:
    raw = getattr(item, 'unit_price', None)
    if raw is not None and str(raw) != '':
        return Decimal(str(raw))
    qty = int(getattr(item, 'quantity', 0) or 0)
    sub = Decimal(str(getattr(item, 'subtotal', 0) or 0))
    if qty > 0:
        return (sub / qty).quantize(Decimal('0.01'))
    return Decimal('0')


def format_sale_items_summary(
    items,
    *,
    max_items: int = 8,
    name_max: int = 18,
) -> str:
    """
    Minified receipt lines for SMS, e.g. ``Soap 2 @ 300, Oil 1 @ 1100``.

    Caps length for single/multi-part SMS; leftover lines become ``+N more``.
    """
    rows = list(items or [])
    if not rows:
        return ''
    parts: list[str] = []
    for item in rows[:max_items]:
        qty = int(getattr(item, 'quantity', 0) or 0)
        unit = _money(_item_unit_price(item))
        parts.append(f'{_item_display_name(item, name_max=name_max)} {qty} @ {unit}')
    extra = len(rows) - max_items
    if extra > 0:
        parts.append(f'+{extra} more')
    return ', '.join(parts)


def format_balance_note(
    balance_owed,
    *,
    show_when_zero: bool | None = None,
) -> str:
    """Balance clause for SMS — empty when zero unless configured to show it."""
    owed = Decimal(str(balance_owed or 0))
    if show_when_zero is None:
        from sales.module_settings import sales_sms_show_balance_when_zero

        show_when_zero = sales_sms_show_balance_when_zero()
    if owed > 0 or (show_when_zero and owed == 0):
        return f' Balance now KES {_money(owed)}.'
    return ''


def format_payment_ref_note(
    reference: str | None,
    *,
    include: bool | None = None,
) -> str:
    """Payment/receipt reference clause — only when configured and non-empty."""
    ref = str(reference or '').strip()
    if not ref:
        return ''
    if include is None:
        from sales.module_settings import sales_sms_include_payment_ref

        include = sales_sms_include_payment_ref()
    if not include:
        return ''
    return f' Ref {ref}.'


def customer_first_name(customer) -> str:
    """Prefer owner / contact person first word; fall back to duka name."""
    if customer is None:
        return 'Customer'
    for raw in (
        getattr(customer, 'owner_name', None),
        getattr(customer, 'contact_person', None),
        getattr(customer, 'name', None),
    ):
        text = str(raw or '').strip()
        if text:
            return sms_cap_name(text.split()[0], fallback='Customer')
    return 'Customer'


def customer_greeting_name(customer) -> str:
    """Collection SMS greeting: use the duka name when set, otherwise first name."""
    if customer is None:
        return 'Customer'
    duka = str(getattr(customer, 'name', None) or '').strip()
    if duka:
        return sms_cap_name(duka, fallback='Customer')
    return customer_first_name(customer)


def render_invoice_sms(
    *,
    customer_name: str,
    invoice_no: str,
    amount,
    public_token: str,
    brand_blurb: str | None = None,
    template: str | None = None,
) -> str:
    link = f'{PUBLIC_INVOICE_BASE_URL.rstrip("/")}/{public_token}'
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_INVOICE)
    return apply_sms_placeholders(
        body,
        customer_name=sms_cap_name(customer_name, fallback='Customer'),
        brand_blurb=brand_blurb or get_brand_blurb(),
        invoice_no=invoice_no,
        amount=f'{amount}',
        link=link,
    )


def render_debt_collection_reminder(
    *,
    template: str | None = None,
    name: str,
    amount,
    store_name: str,
) -> str:
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_DEBT_REMINDER)
    return apply_sms_placeholders(
        body,
        name=sms_cap_name(name, fallback='Customer'),
        amount=_money(amount),
        store_name=sms_cap_name(store_name, fallback='us', first_word_only=False),
    )


# Back-compat alias used by older tests / debt reminder with payment link.
def render_debt_reminder_sms(
    *,
    customer_name: str,
    amount,
    public_token: str,
    brand_blurb: str | None = None,
) -> str:
    link = f'{PUBLIC_INVOICE_BASE_URL.rstrip("/")}/{public_token}'
    return apply_sms_placeholders(
        'Hi {customer_name}. Reminder: you owe KES {amount}. {brand_blurb} Settle here: {link}',
        customer_name=sms_cap_name(customer_name, fallback='Customer'),
        brand_blurb=brand_blurb or get_brand_blurb(),
        amount=f'{amount}',
        link=link,
    )


def render_sale_completed_sms(
    *,
    first_name: str,
    sale_number: str,
    total,
    paid,
    balance_owed=None,
    items=None,
    items_summary: str | None = None,
    payment_reference: str | None = None,
    template: str | None = None,
) -> str:
    balance_note = format_balance_note(balance_owed)
    payment_ref = format_payment_ref_note(payment_reference)
    summary = (items_summary if items_summary is not None else format_sale_items_summary(items)).strip()
    # Trailing ". " so the default template reads cleanly when items are present or absent.
    items_clause = f'{summary}. ' if summary else ''
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_SALE_COMPLETED)
    return apply_sms_placeholders(
        body,
        first_name=sms_cap_name(first_name, fallback='Customer'),
        sale_number=format_sale_number_for_sms(sale_number),
        items=items_clause,
        total=_money(total),
        paid=_money(paid),
        payment_ref=payment_ref,
        balance_note=balance_note,
        # Older templates may still use {debt_bit}
        debt_bit=balance_note,
    )


def render_debt_increase_sms(
    *,
    first_name: str,
    amount,
    balance_owed,
    template: str | None = None,
) -> str:
    balance_note = format_balance_note(balance_owed)
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_DEBT_INCREASE)
    return apply_sms_placeholders(
        body,
        first_name=sms_cap_name(first_name, fallback='Customer'),
        amount=_money(amount),
        balance=_money(balance_owed),
        balance_note=balance_note,
    )


def render_debt_settlement_sms(
    *,
    first_name: str,
    amount,
    balance_owed,
    payment_reference: str | None = None,
    template: str | None = None,
) -> str:
    balance_note = format_balance_note(balance_owed)
    payment_ref = format_payment_ref_note(payment_reference)
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_DEBT_SETTLEMENT)
    return apply_sms_placeholders(
        body,
        first_name=sms_cap_name(first_name, fallback='Customer'),
        amount=_money(amount),
        balance=_money(balance_owed),
        payment_ref=payment_ref,
        balance_note=balance_note,
    )


def render_customer_week_sms(
    *,
    name: str,
    store_name: str,
    offer: str | None = None,
    template: str | None = None,
) -> str:
    """Customer Week promo SMS — first of the promo template family."""
    offer_text = str(offer or '').strip()
    if offer_text and not offer_text.endswith((' ', '\n')):
        offer_text = f'{offer_text} '
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_CUSTOMER_WEEK)
    return apply_sms_placeholders(
        body,
        name=sms_cap_name(name, fallback='Customer'),
        store_name=sms_cap_name(store_name, fallback='us', first_word_only=False),
        offer=offer_text,
    )


CUSTOMER_WELCOME_SMS_MAX_CHARS = 300


def render_customer_welcome_sms(
    *,
    name: str,
    store_name: str,
    template: str | None = None,
) -> str:
    """Welcome SMS when a duka is registered — hard-capped at 300 characters."""
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_CUSTOMER_WELCOME)
    text = apply_sms_placeholders(
        body,
        name=sms_cap_name(name, fallback='Customer'),
        store_name=sms_cap_name(store_name, fallback='Omuwenga', first_word_only=False),
    ).strip()
    if len(text) > CUSTOMER_WELCOME_SMS_MAX_CHARS:
        text = text[: CUSTOMER_WELCOME_SMS_MAX_CHARS - 1].rstrip() + '…'
    return text


# Re-export for callers that imported the constant name.
DEFAULT_DEBT_COLLECTION_TEMPLATE = (
    'Hi {name}, hope you are well. Your balance with {store_name} is KES {amount}. '
    'Settling keeps your orders moving and stock ready for your next delivery. '
    'Asante — we value your business.'
)
