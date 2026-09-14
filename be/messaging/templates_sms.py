"""SMS template rendering (Misspat-style variables)."""

from payments.config import BRAND_BLURB, PUBLIC_INVOICE_BASE_URL


INVOICE_TEMPLATE = (
    'Hi {customer_name}. {brand_blurb} '
    'Invoice {invoice_no} for KES {amount}. Pay/view: {link}'
)

DEBT_REMINDER_TEMPLATE = (
    'Hi {customer_name}. Reminder: you owe KES {amount}. '
    '{brand_blurb} Settle here: {link}'
)


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
        brand_blurb=brand_blurb or BRAND_BLURB,
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
        brand_blurb=brand_blurb or BRAND_BLURB,
        amount=f'{amount}',
        link=link,
    )
