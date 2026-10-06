"""SMS template rendering — defaults + DB overrides via template_catalog."""

from decimal import Decimal

from payments.config import PUBLIC_INVOICE_BASE_URL, get_brand_blurb

from .models import SmsTemplate
from .template_catalog import get_template_body


def _money(amount) -> str:
    try:
        value = Decimal(str(amount or 0)).quantize(Decimal('0.01'))
    except Exception:
        value = Decimal('0.00')
    text = f'{value:f}'
    if text.endswith('.00'):
        return text[:-3]
    return text.rstrip('0').rstrip('.') if '.' in text else text


def apply_sms_placeholders(template: str, **values) -> str:
    """Replace {key} tokens without str.format (avoids brace crashes)."""
    body = template or ''
    for key, value in values.items():
        body = body.replace('{' + key + '}', str(value))
    return body


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
            return text.split()[0]
    return 'Customer'


def customer_greeting_name(customer) -> str:
    """Collection SMS greeting: use the duka name when set, otherwise first name."""
    if customer is None:
        return 'Customer'
    duka = str(getattr(customer, 'name', None) or '').strip()
    if duka:
        return duka
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
        customer_name=customer_name or 'Customer',
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
        name=name or 'Customer',
        amount=_money(amount),
        store_name=store_name or 'us',
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
        customer_name=customer_name or 'Customer',
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
    template: str | None = None,
) -> str:
    owed = Decimal(str(balance_owed or 0))
    if owed > 0:
        balance_note = f' Balance now KES {_money(owed)}.'
    else:
        balance_note = ''
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_SALE_COMPLETED)
    return apply_sms_placeholders(
        body,
        first_name=first_name or 'Customer',
        sale_number=sale_number or 'sale',
        total=_money(total),
        paid=_money(paid),
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
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_DEBT_INCREASE)
    return apply_sms_placeholders(
        body,
        first_name=first_name or 'Customer',
        amount=_money(amount),
        balance=_money(balance_owed),
    )


def render_debt_settlement_sms(
    *,
    first_name: str,
    amount,
    balance_owed,
    template: str | None = None,
) -> str:
    body = (template or '').strip() or get_template_body(SmsTemplate.KEY_DEBT_SETTLEMENT)
    return apply_sms_placeholders(
        body,
        first_name=first_name or 'Customer',
        amount=_money(amount),
        balance=_money(balance_owed),
    )


# Re-export for callers that imported the constant name.
DEFAULT_DEBT_COLLECTION_TEMPLATE = (
    'Hi {name}, hope you are well. Your balance with {store_name} is KES {amount}. '
    'Settling keeps your orders moving and stock ready for your next delivery. '
    'Asante — we value your business.'
)
