"""
Registry of every customer SMS the system can send.

Each entry has a code default. Operators can override the body in SmsTemplate;
get_template_body() returns the override when present, otherwise the default.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import SmsTemplate


@dataclass(frozen=True)
class SmsTemplateSpec:
    key: str
    label: str
    description: str
    default_body: str
    placeholders: tuple[str, ...]
    sample: dict[str, str]
    category: str  # sales | debt | payments | promo


# Keep bodies short (ideally ≤160 chars when rendered) and collections-friendly.
SMS_TEMPLATE_SPECS: dict[str, SmsTemplateSpec] = {
    SmsTemplate.KEY_SALE_COMPLETED: SmsTemplateSpec(
        key=SmsTemplate.KEY_SALE_COMPLETED,
        label='Sale completed',
        description=(
            'Minified receipt SMS when a sale is finalized. '
            '{items} is the goods summary (e.g. Soap 2 @ 300, Oil 1 @ 1100). '
            '{payment_ref} is the receipt/M-PESA reference when present (configurable). '
            '{balance_note} is empty when balance is zero unless configured to show it.'
        ),
        default_body=(
            'Hi {first_name}, your order {sale_number}.\n{items}'
            'Total KES {total}. Paid KES {paid}.{payment_ref}{balance_note} Karibu.'
        ),
        placeholders=(
            'first_name',
            'sale_number',
            'items',
            'total',
            'paid',
            'payment_ref',
            'balance_note',
        ),
        sample={
            'first_name': 'Jane',
            'sale_number': 'S-0001',
            'items': 'Soap 2 @ 300, Cooking oil 1 @ 1100. ',
            'total': '1500',
            'paid': '1000',
            'payment_ref': ' Ref QHX1ABC2DE.',
            'balance_note': ' Balance now KES 500.',
        },
        category='sales',
    ),
    SmsTemplate.KEY_DEBT_SETTLEMENT: SmsTemplateSpec(
        key=SmsTemplate.KEY_DEBT_SETTLEMENT,
        label='Debt payment received',
        description=(
            'Sent when a customer settles part or all of their wallet debt. '
            '{payment_ref} is the receipt/M-PESA reference when present. '
            '{balance_note} is omitted when the balance is cleared (unless configured).'
        ),
        default_body=(
            'Hi {first_name}, we received KES {amount}.{payment_ref}{balance_note} Asante.'
        ),
        placeholders=('first_name', 'amount', 'payment_ref', 'balance_note', 'balance'),
        sample={
            'first_name': 'Jane',
            'amount': '200',
            'payment_ref': ' Ref QHX1ABC2DE.',
            'balance_note': ' Balance now KES 300.',
            'balance': '300',
        },
        category='debt',
    ),
    SmsTemplate.KEY_DEBT_INCREASE: SmsTemplateSpec(
        key=SmsTemplate.KEY_DEBT_INCREASE,
        label='Debt increased',
        description=(
            'Sent when debt is added outside a sale-complete notice. '
            '{balance_note} is omitted when balance is zero unless configured.'
        ),
        default_body=(
            'Hi {first_name}, KES {amount} was added to your account.{balance_note} Karibu.'
        ),
        placeholders=('first_name', 'amount', 'balance_note', 'balance'),
        sample={
            'first_name': 'Jane',
            'amount': '400',
            'balance_note': ' Balance now KES 900.',
            'balance': '900',
        },
        category='debt',
    ),
    SmsTemplate.KEY_DEBT_REMINDER: SmsTemplateSpec(
        key=SmsTemplate.KEY_DEBT_REMINDER,
        label='Debt collection reminder',
        description=(
            'Bulk Monday-style reminders. {name} is the duka name when set, '
            'otherwise the owner first name.'
        ),
        default_body=(
            'Hi {name}, hope you are well. Your balance with {store_name} is KES {amount}. '
            'Settling keeps your orders moving and stock ready for your next delivery. '
            'Asante — we value your business.'
        ),
        placeholders=('name', 'amount', 'store_name'),
        sample={
            'name': 'Mama Mboga',
            'amount': '2500',
            'store_name': 'Omuwenga Suppliers',
        },
        category='debt',
    ),
    SmsTemplate.KEY_INVOICE: SmsTemplateSpec(
        key=SmsTemplate.KEY_INVOICE,
        label='Invoice / payment link',
        description='Sent with a public invoice or payment link.',
        default_body=(
            'Hi {customer_name}. {brand_blurb} '
            'Invoice {invoice_no} for KES {amount}. Pay/view: {link}'
        ),
        placeholders=('customer_name', 'brand_blurb', 'invoice_no', 'amount', 'link'),
        sample={
            'customer_name': 'Jane',
            'brand_blurb': 'Thank you for shopping with Omuwenga Suppliers.',
            'invoice_no': 'INV-100',
            'amount': '3200',
            'link': 'https://example.com/i/abc',
        },
        category='payments',
    ),
    SmsTemplate.KEY_CUSTOMER_WEEK: SmsTemplateSpec(
        key=SmsTemplate.KEY_CUSTOMER_WEEK,
        label='Customer Week promo',
        description=(
            'Promotional blast for Customer Week. '
            '{name} is the short greeting name (first word, tags in [brackets] removed). '
            '{offer} is optional promo detail — leave blank or edit before sending. '
            'More promo templates (seasonal, flash sale) can follow this pattern.'
        ),
        default_body=(
            'Hi {name}, it is Customer Week at {store_name}! '
            '{offer}'
            'Visit us or order as usual for exclusive deals this week. '
            'Asante — karibu tena.'
        ),
        placeholders=('name', 'store_name', 'offer'),
        sample={
            'name': 'Mwangi',
            'store_name': 'Omuwenga Suppliers',
            'offer': 'Special prices on fast movers. ',
        },
        category='promo',
    ),
    SmsTemplate.KEY_CUSTOMER_WELCOME: SmsTemplateSpec(
        key=SmsTemplate.KEY_CUSTOMER_WELCOME,
        label='Customer welcome',
        description=(
            'Sent once when a duka is registered. Keep the rendered body ≤300 characters. '
            '{name} is the short greeting name; {store_name} is the shop name.'
        ),
        default_body=(
            'Hi {name}, karibu to {store_name}. You are part of our larger network. '
            'We will send updates on items we have, new price alerts, and other news. Asante.'
        ),
        placeholders=('name', 'store_name'),
        sample={
            'name': 'Jane',
            'store_name': 'Omuwenga',
        },
        category='promo',
    ),
}


def all_template_specs() -> list[SmsTemplateSpec]:
    return list(SMS_TEMPLATE_SPECS.values())


def get_spec(key: str) -> SmsTemplateSpec | None:
    return SMS_TEMPLATE_SPECS.get(key)


def get_default_body(key: str) -> str:
    spec = SMS_TEMPLATE_SPECS.get(key)
    return spec.default_body if spec else ''


def get_template_body(key: str) -> str:
    """Stored override if present, otherwise the code default."""
    try:
        row = SmsTemplate.objects.filter(key=key).only('body').first()
    except Exception:
        # SimpleTestCase / no DB — use code default.
        return get_default_body(key)
    body = (row.body if row else '') or ''
    body = body.strip()
    if body:
        return body
    return get_default_body(key)


def is_customized(key: str) -> bool:
    try:
        row = SmsTemplate.objects.filter(key=key).only('body').first()
    except Exception:
        return False
    if not row:
        return False
    stored = (row.body or '').strip()
    return bool(stored) and stored != get_default_body(key)
