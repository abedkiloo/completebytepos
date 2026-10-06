"""SMS template rendering — keep customer texts short."""

from decimal import Decimal

from payments.config import PUBLIC_INVOICE_BASE_URL, get_brand_blurb


INVOICE_TEMPLATE = (
    'Hi {customer_name}. {brand_blurb} '
    'Invoice {invoice_no} for KES {amount}. Pay/view: {link}'
)

DEBT_REMINDER_TEMPLATE = (
    'Hi {customer_name}. Reminder: you owe KES {amount}. '
    '{brand_blurb} Settle here: {link}'
)

# Sale + debt — first name only, no links (avoid over-messaging).
SALE_COMPLETED_TEMPLATE = (
    'Hi {first_name}, sale {sale_number} of KES {total} is complete. '
    'Paid KES {paid}.{debt_bit} Karibu.'
)

DEBT_INCREASE_TEMPLATE = (
    'Hi {first_name}, KES {amount} was added to your account. '
    'Balance now KES {balance}. Karibu.'
)

DEBT_SETTLEMENT_TEMPLATE = (
    'Hi {first_name}, we received KES {amount}. '
    'Balance now KES {balance}. Asante.'
)


def _money(amount) -> str:
    try:
        value = Decimal(str(amount or 0)).quantize(Decimal('0.01'))
    except Exception:
        value = Decimal('0.00')
    text = f'{value:f}'
    if text.endswith('.00'):
        return text[:-3]
    return text.rstrip('0').rstrip('.') if '.' in text else text


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


def render_invoice_sms(
    *,
    customer_name: str,
    invoice_no: str,
    amount,
    public_token: str,
    brand_blurb: str | None = None,
) -> str:
    link = f'{PUBLIC_INVOICE_BASE_URL.rstrip("/")}/{public_token}'
    return INVOICE_TEMPLATE.format(
        customer_name=customer_name or 'Customer',
        brand_blurb=brand_blurb or get_brand_blurb(),
        invoice_no=invoice_no,
        amount=f'{amount}',
        link=link,
    )


def render_debt_reminder_sms(
    *,
    customer_name: str,
    amount,
    public_token: str,
    brand_blurb: str | None = None,
) -> str:
    link = f'{PUBLIC_INVOICE_BASE_URL.rstrip("/")}/{public_token}'
    return DEBT_REMINDER_TEMPLATE.format(
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
) -> str:
    owed = Decimal(str(balance_owed or 0))
    if owed > 0:
        debt_bit = f' Balance now KES {_money(owed)}.'
    else:
        debt_bit = ''
    return SALE_COMPLETED_TEMPLATE.format(
        first_name=first_name or 'Customer',
        sale_number=sale_number or 'sale',
        total=_money(total),
        paid=_money(paid),
        debt_bit=debt_bit,
    )


def render_debt_increase_sms(*, first_name: str, amount, balance_owed) -> str:
    return DEBT_INCREASE_TEMPLATE.format(
        first_name=first_name or 'Customer',
        amount=_money(amount),
        balance=_money(balance_owed),
    )


def render_debt_settlement_sms(*, first_name: str, amount, balance_owed) -> str:
    return DEBT_SETTLEMENT_TEMPLATE.format(
        first_name=first_name or 'Customer',
        amount=_money(amount),
        balance=_money(balance_owed),
    )
