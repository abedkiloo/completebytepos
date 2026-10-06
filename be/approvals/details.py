"""
Readable details for a pending change so a checker sees everything before approving.

Shape (all optional)::

    {"sections": [
        {"title": "Sale", "facts": [{"label": "Customer", "value": "Jane", "kind": "text"}]},
        {"title": "Items", "lines": [{"name": "Shoe", "variant": "42 / Black",
                                      "quantity": 2, "unit_price": "500.00",
                                      "subtotal": "1000.00"}]},
    ]}

``kind`` is ``text`` (default), ``money`` or ``datetime``.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from approvals.models import PendingChange
from approvals.registry import (
    ACTION_DEBT_COLLECTION,
    ACTION_SALE_BACKFILL,
    ACTION_SALE_REFUND,
)

PAYMENT_LABELS = {'cash': 'Cash', 'mpesa': 'M-PESA', 'card': 'Card', 'other': 'Other'}
SALE_TYPE_LABELS = {'pos': 'POS sale', 'normal': 'Normal sale (invoice)'}


def _dec(value) -> Decimal:
    try:
        return Decimal(str(value if value not in (None, '') else '0'))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _fact(label: str, value: Any, kind: str = 'text') -> dict | None:
    if value is None or value == '':
        return None
    if kind == 'money':
        value = str(_dec(value))
    elif kind == 'datetime' and hasattr(value, 'isoformat'):
        value = value.isoformat()
    else:
        value = str(value)
    return {'label': label, 'value': value, 'kind': kind}


def _facts(*rows) -> list[dict]:
    return [row for row in rows if row]


def _section(title: str, *, facts: Iterable | None = None, lines: list | None = None) -> dict | None:
    section: dict = {'title': title}
    if facts:
        section['facts'] = [f for f in facts if f]
    if lines:
        section['lines'] = lines
    if not section.get('facts') and not section.get('lines'):
        return None
    return section


def _user_label(user) -> str:
    if not user:
        return ''
    return user.get_full_name().strip() or user.username


def _variant_label(size=None, color=None, fallback_sku: str = '') -> str:
    bits = [getattr(size, 'name', None), getattr(color, 'name', None)]
    label = ' / '.join(b for b in bits if b)
    return label or fallback_sku or ''


def _format_qty(qty: Decimal) -> str:
    """Plain quantity text — never scientific notation (``Decimal.normalize`` → ``1E+1``)."""
    if qty == qty.to_integral():
        return str(int(qty))
    text = format(qty, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def _line(name, variant, quantity, unit_price, subtotal=None) -> dict:
    qty = _dec(quantity)
    price = _dec(unit_price)
    total = _dec(subtotal) if subtotal not in (None, '') else qty * price
    return {
        'name': name or 'Item',
        'variant': variant or '',
        'quantity': _format_qty(qty),
        'unit_price': str(price),
        'subtotal': str(total),
    }


def _customer_facts(customer) -> list[dict | None]:
    if not customer:
        return [{'label': 'Customer', 'value': 'Walk-in (no customer)', 'kind': 'text'}]
    wallet = _dec(customer.wallet_balance)
    return [
        _fact('Customer', customer.name),
        _fact('Phone', getattr(customer, 'phone', '')),
        _fact('Wallet debt now', -wallet, 'money') if wallet < 0 else None,
        _fact('Wallet credit now', wallet, 'money') if wallet > 0 else None,
    ]


def sale_sections(sale, *, payment_payload: dict | None = None) -> list[dict]:
    """Header, items, and money for one sale."""
    payload = payment_payload or {}
    total = _dec(sale.total)
    paid = _dec(payload.get('amount_paid', sale.amount_paid))
    method = payload.get('payment_method') or sale.payment_method
    balance = total - paid

    header = _section('Sale', facts=_facts(
        _fact('Sale number', sale.sale_number),
        _fact('Sale date', sale.occurred_at or sale.created_at, 'datetime'),
        _fact('Sale type', SALE_TYPE_LABELS.get(sale.sale_type, sale.sale_type)),
        _fact('Sold by', _user_label(sale.served_by or sale.cashier)),
        _fact('Rung up by', _user_label(sale.cashier))
        if sale.served_by_id and sale.served_by_id != sale.cashier_id else None,
        *_customer_facts(sale.customer),
        _fact('Delivery', sale.delivery_method),
        _fact('Ship to', sale.shipping_location or sale.shipping_address),
        _fact('Notes', sale.notes),
        _fact('Past-sale reason', getattr(sale, 'backfill_reason', '')),
    ))

    lines = [
        _line(
            item.product.name if item.product_id else '',
            _variant_label(item.size, item.color, getattr(item.variant, 'sku', '') if item.variant_id else ''),
            item.quantity,
            item.unit_price,
            item.subtotal,
        )
        for item in sale.items.select_related('product', 'variant', 'size', 'color').all()
    ]
    items = _section('Items', lines=lines)

    wallet_used = _dec(payload.get('wallet_amount_locked') or (
        payload.get('wallet_amount') if payload.get('use_wallet') else 0
    ))
    money = _section('Money', facts=_facts(
        _fact('Subtotal', sale.subtotal, 'money'),
        _fact('Discount', sale.discount_amount, 'money') if _dec(sale.discount_amount) else None,
        _fact('Tax', sale.tax_amount, 'money') if _dec(sale.tax_amount) else None,
        _fact('Delivery cost', sale.delivery_cost, 'money') if _dec(sale.delivery_cost) else None,
        _fact('Total', total, 'money'),
        _fact('Payment method', PAYMENT_LABELS.get(method, method)),
        _fact('Payment reference', payload.get('payment_reference') or sale.payment_reference),
        _fact('Amount paid', paid, 'money'),
        _fact('Paid from wallet', wallet_used, 'money') if wallet_used > 0 else None,
        _fact('Balance left as debt', balance, 'money') if balance > 0 else None,
        _fact('Change given', sale.change, 'money') if _dec(sale.change) > 0 else None,
        _fact('Invoice due date', (payload.get('invoice') or {}).get('due_date'))
        if isinstance(payload.get('invoice'), dict) else None,
    ))
    return [s for s in (header, items, money) if s]


def _sale_for(change: PendingChange):
    from sales.models import Sale

    try:
        return (
            Sale.objects.select_related('customer', 'cashier', 'served_by')
            .filter(pk=int(change.entity_id))
            .first()
        )
    except (TypeError, ValueError):
        return None


def _refund_sections(change: PendingChange, sale) -> list[dict]:
    from sales.refunds import SaleRefundService

    payload = change.apply_payload or {}
    try:
        resolved = SaleRefundService()._resolve_refund_lines(
            sale, items=payload.get('items') or None, full=bool(payload.get('full')),
        )
    except Exception:
        return []
    lines = []
    for row in resolved:
        item = row['sale_item']
        lines.append(_line(
            item.product.name if item.product_id else '',
            _variant_label(item.size, item.color),
            row['quantity'],
            item.unit_price,
            row.get('subtotal'),
        ))
    section = _section('Items to return', lines=lines)
    return [section] if section else []


def _backfill_sections(change: PendingChange) -> list[dict]:
    from django.contrib.auth.models import User
    from products.models import Product, ProductVariant
    from products.stock_utils import sellable_unit_price
    from sales.models import Customer

    payload = change.apply_payload or {}
    customer = None
    if payload.get('customer_id'):
        customer = Customer.objects.filter(pk=payload['customer_id']).first()
    served_by = None
    if payload.get('served_by_id'):
        served_by = User.objects.filter(pk=payload['served_by_id']).first()

    lines = []
    total = Decimal('0')
    for row in payload.get('items') or []:
        product = Product.objects.filter(pk=row.get('product_id')).first()
        variant = None
        if row.get('variant_id'):
            variant = (
                ProductVariant.objects.select_related('size', 'color')
                .filter(pk=row['variant_id']).first()
            )
        try:
            price = (
                row.get('unit_price')
                if row.get('unit_price') not in (None, '')
                else (sellable_unit_price(product, variant) if product else 0)
            )
        except Exception:
            price = 0
        line = _line(
            product.name if product else f"Product #{row.get('product_id')}",
            _variant_label(getattr(variant, 'size', None), getattr(variant, 'color', None),
                           getattr(variant, 'sku', '')) if variant else '',
            row.get('quantity', 1),
            price,
        )
        total += _dec(line['subtotal'])
        lines.append(line)

    discount = _dec(payload.get('discount_amount'))
    tax = _dec(payload.get('tax_amount'))
    delivery = _dec(payload.get('delivery_cost'))
    grand = total - discount + tax + delivery
    paid = _dec(payload.get('amount_paid'))
    method = payload.get('payment_method') or 'cash'

    header = _section('Past sale', facts=_facts(
        _fact('Sale date', payload.get('occurred_at'), 'datetime'),
        _fact('Sale type', SALE_TYPE_LABELS.get(payload.get('sale_type'), payload.get('sale_type'))),
        _fact('Sold by', _user_label(served_by)),
        *(_customer_facts(customer) if customer or not payload.get('customer_name')
          else [_fact('Customer', payload.get('customer_name'))]),
        _fact('Notes', payload.get('notes')),
        _fact('Reason', payload.get('backfill_reason')),
    ))
    money = _section('Money', facts=_facts(
        _fact('Items total', total, 'money'),
        _fact('Discount', discount, 'money') if discount else None,
        _fact('Tax', tax, 'money') if tax else None,
        _fact('Delivery cost', delivery, 'money') if delivery else None,
        _fact('Total', grand, 'money'),
        _fact('Payment method', PAYMENT_LABELS.get(method, method)),
        _fact('Payment reference', payload.get('payment_reference')),
        _fact('Amount paid', paid, 'money'),
        _fact('Balance left as debt', grand - paid, 'money') if grand - paid > 0 else None,
    ))
    return [s for s in (header, _section('Items', lines=lines), money) if s]


def _debt_collection_sections(change: PendingChange) -> list[dict]:
    from sales.models import Customer

    payload = change.apply_payload or {}
    customer = None
    try:
        customer = Customer.objects.filter(pk=int(change.entity_id)).first()
    except (TypeError, ValueError):
        pass
    amount = _dec(payload.get('amount'))
    method = payload.get('payment_method') or 'cash'
    before = _dec(
        customer.wallet_balance if customer
        else (change.original_values or {}).get('wallet_balance')
    )
    after = before + amount
    return [s for s in (
        _section('Customer', facts=_facts(
            _fact('Customer', customer.name if customer else change.entity_repr),
            _fact('Phone', getattr(customer, 'phone', '') if customer else ''),
            _fact('Debt owed now', -before, 'money') if before < 0 else _fact('Wallet credit now', before, 'money'),
            _fact('Debt after approval', -after, 'money') if after < 0
            else _fact('Wallet after approval', after, 'money'),
        )),
        _section('Collection', facts=_facts(
            _fact('Amount collected', amount, 'money'),
            _fact('Payment method', PAYMENT_LABELS.get(method, method)),
            _fact('Reference', payload.get('reference')),
            _fact('Notes', payload.get('notes')),
            _fact('Collected by', _user_label(change.made_by)),
            _fact('Collected at', change.made_at, 'datetime'),
        )),
    ) if s]


def _product_sections(change: PendingChange) -> list[dict]:
    from products.models import Product, ProductVariant

    try:
        pk = int(change.entity_id)
    except (TypeError, ValueError):
        return []
    if change.entity_type == 'products.ProductVariant':
        variant = (
            ProductVariant.objects.select_related('product', 'size', 'color')
            .filter(pk=pk).first()
        )
        if not variant:
            return []
        section = _section('Product now', facts=_facts(
            _fact('Product', variant.product.name),
            _fact('Variant', _variant_label(variant.size, variant.color)),
            _fact('SKU', variant.sku),
            _fact('Selling price', variant.price, 'money') if variant.price is not None else None,
            _fact('Cost', variant.cost, 'money') if variant.cost is not None else None,
            _fact('Stock on hand', variant.stock_quantity),
        ))
        return [section] if section else []
    product = Product.objects.select_related('category').filter(pk=pk).first()
    if not product:
        return []
    section = _section('Product now', facts=_facts(
        _fact('Product', product.name),
        _fact('SKU', product.sku),
        _fact('Category', getattr(product.category, 'name', '')),
        _fact('Selling price', product.price, 'money'),
        _fact('Cost', product.cost, 'money'),
        _fact('Stock on hand', product.stock_quantity),
    ))
    return [section] if section else []


def pending_change_details(change: PendingChange) -> dict | None:
    sections: list[dict] = []
    if change.action_type == ACTION_DEBT_COLLECTION:
        sections = _debt_collection_sections(change)
    elif change.action_type == ACTION_SALE_BACKFILL:
        sections = _backfill_sections(change)
    elif change.entity_type == 'sales.Sale':
        sale = _sale_for(change)
        if sale:
            payload = change.apply_payload if change.action_type == 'sale_complete' else None
            sections = sale_sections(sale, payment_payload=payload)
            if change.action_type == ACTION_SALE_REFUND:
                sections += _refund_sections(change, sale)
    elif change.entity_type in ('products.Product', 'products.ProductVariant'):
        sections = _product_sections(change)
    return {'sections': sections} if sections else None
