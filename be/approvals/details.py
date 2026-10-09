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
    ACTION_CATEGORY_DEACTIVATE,
    ACTION_CATEGORY_DELETE,
    ACTION_DEBT_COLLECTION,
    ACTION_PAYMENT_METHODS,
    ACTION_RECEIPT_LEGAL,
    ACTION_ROLE_PERMISSIONS,
    ACTION_SALE_BACKFILL,
    ACTION_SALE_REFUND,
    ACTION_STOCK_ADJUST,
    ACTION_STOCK_PURCHASE,
    ACTION_STOCK_TRANSFER,
    ACTION_STORE_SETTINGS,
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


def _iter_sale_items(sale):
    """Prefer prefetched items; only hit the DB when the cache is cold."""
    cache = getattr(sale, '_prefetched_objects_cache', {})
    if 'items' in cache:
        return sale.items.all()
    return sale.items.select_related('product', 'variant', 'size', 'color').all()


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
        for item in _iter_sale_items(sale)
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


def _sale_for(change: PendingChange, cache=None):
    from sales.models import Sale

    try:
        pk = int(change.entity_id)
    except (TypeError, ValueError):
        return None
    if cache is not None and pk in cache.sales:
        return cache.sales[pk]
    return (
        Sale.objects.select_related('customer', 'cashier', 'served_by')
        .prefetch_related(
            'items__product', 'items__variant', 'items__size', 'items__color',
        )
        .filter(pk=pk)
        .first()
    )


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


def _backfill_sections(change: PendingChange, cache=None) -> list[dict]:
    from django.contrib.auth.models import User
    from products.models import Product, ProductVariant
    from products.stock_utils import sellable_unit_price
    from sales.models import Customer

    payload = change.apply_payload or {}
    customer = None
    if payload.get('customer_id'):
        cid = int(payload['customer_id'])
        customer = (cache.customers.get(cid) if cache else None) or Customer.objects.filter(pk=cid).first()
    served_by = None
    if payload.get('served_by_id'):
        served_by = User.objects.filter(pk=payload['served_by_id']).first()

    item_rows = list(payload.get('items') or [])
    product_ids = {
        row.get('product_id')
        for row in item_rows
        if row.get('product_id') not in (None, '')
    }
    variant_ids = {
        row.get('variant_id')
        for row in item_rows
        if row.get('variant_id') not in (None, '')
    }
    if cache is not None:
        products_by_id = {pid: cache.products[pid] for pid in product_ids if pid in cache.products}
        variants_by_id = {vid: cache.variants[vid] for vid in variant_ids if vid in cache.variants}
        missing_products = product_ids - set(products_by_id)
        missing_variants = variant_ids - set(variants_by_id)
    else:
        products_by_id = {}
        variants_by_id = {}
        missing_products = product_ids
        missing_variants = variant_ids
    if missing_products:
        products_by_id.update({
            p.pk: p for p in Product.objects.filter(pk__in=missing_products)
        })
    if missing_variants:
        variants_by_id.update({
            v.pk: v
            for v in ProductVariant.objects.select_related('size', 'color').filter(
                pk__in=missing_variants
            )
        })

    lines = []
    total = Decimal('0')
    for row in item_rows:
        product = products_by_id.get(row.get('product_id'))
        variant = variants_by_id.get(row.get('variant_id')) if row.get('variant_id') else None
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


def _debt_collection_sections(change: PendingChange, cache=None) -> list[dict]:
    from sales.models import Customer

    payload = change.apply_payload or {}
    customer = None
    try:
        pk = int(change.entity_id)
        customer = (cache.customers.get(pk) if cache else None) or Customer.objects.filter(pk=pk).first()
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


def _product_sections(change: PendingChange, cache=None) -> list[dict]:
    from products.models import Product, ProductVariant

    try:
        pk = int(change.entity_id)
    except (TypeError, ValueError):
        return []
    if change.entity_type == 'products.ProductVariant':
        variant = (cache.variants.get(pk) if cache else None) or (
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
    product = (cache.products.get(pk) if cache else None) or (
        Product.objects.select_related('category').filter(pk=pk).first()
    )
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


def _category_sections(change: PendingChange, cache=None) -> list[dict]:
    from products.models import Category

    try:
        pk = int(change.entity_id)
    except (TypeError, ValueError):
        return []
    category = (cache.categories.get(pk) if cache else None) or Category.objects.filter(pk=pk).first()
    name = getattr(category, 'name', None) or change.entity_repr
    proposed = change.proposed_values or {}
    original = change.original_values or {}
    section = _section('Category', facts=_facts(
        _fact('Category', name),
        _fact('Active now', 'Yes' if getattr(category, 'is_active', None) else 'No')
        if category is not None else None,
        _fact('Requested active', 'Yes' if proposed.get('is_active') else 'No')
        if 'is_active' in proposed else None,
        _fact('Was active', 'Yes' if original.get('is_active') else 'No')
        if 'is_active' in original else None,
        _fact('Action', 'Delete category')
        if change.action_type == ACTION_CATEGORY_DELETE else (
            _fact('Action', 'Deactivate category')
            if change.action_type == ACTION_CATEGORY_DEACTIVATE else None
        ),
    ))
    return [section] if section else []


def _stock_sections(change: PendingChange, cache=None) -> list[dict]:
    from products.models import Product, ProductVariant
    from settings.models import Branch

    payload = change.apply_payload or {}
    product = None
    variant = None
    if payload.get('product_id'):
        pid = int(payload['product_id'])
        product = (cache.products.get(pid) if cache else None) or (
            Product.objects.select_related('category').filter(pk=pid).first()
        )
    if payload.get('variant_id'):
        vid = int(payload['variant_id'])
        variant = (cache.variants.get(vid) if cache else None) or (
            ProductVariant.objects.select_related('product', 'size', 'color')
            .filter(pk=vid).first()
        )
        if variant and not product:
            product = variant.product

    branch = None
    if payload.get('branch_id'):
        bid = int(payload['branch_id'])
        branch = (cache.branches.get(bid) if cache else None) or Branch.objects.filter(pk=bid).first()
    to_branch = None
    if payload.get('to_branch_id'):
        tid = int(payload['to_branch_id'])
        to_branch = (cache.branches.get(tid) if cache else None) or Branch.objects.filter(pk=tid).first()

    action_labels = {
        ACTION_STOCK_ADJUST: 'Stock adjustment',
        ACTION_STOCK_PURCHASE: 'Stock purchase',
        ACTION_STOCK_TRANSFER: 'Stock transfer',
    }
    qty = payload.get('quantity')
    stock_now = None
    if variant is not None:
        stock_now = variant.stock_quantity
    elif product is not None:
        stock_now = product.stock_quantity

    section = _section('Stock movement', facts=_facts(
        _fact('Type', action_labels.get(change.action_type, change.action_type)),
        _fact('Product', product.name if product else change.entity_repr),
        _fact(
            'Variant',
            _variant_label(
                getattr(variant, 'size', None),
                getattr(variant, 'color', None),
                getattr(variant, 'sku', ''),
            ),
        ) if variant else None,
        _fact('SKU', getattr(product, 'sku', '') if product else ''),
        _fact('Quantity', _format_qty(_dec(qty)) if qty not in (None, '') else None),
        _fact('Unit cost', payload.get('unit_cost'), 'money')
        if payload.get('unit_cost') not in (None, '') else None,
        _fact('Unit sell price', payload.get('unit_sell_price'), 'money')
        if payload.get('unit_sell_price') not in (None, '') else None,
        _fact('Stock on hand now', stock_now),
        _fact('Branch', getattr(branch, 'name', '') if branch else ''),
        _fact('From branch', getattr(branch, 'name', '') if branch else '')
        if change.action_type == ACTION_STOCK_TRANSFER else None,
        _fact('To branch', getattr(to_branch, 'name', '') if to_branch else '')
        if change.action_type == ACTION_STOCK_TRANSFER else None,
        _fact('Reference', payload.get('reference')),
        _fact('Notes', payload.get('notes')),
        _fact('Requested by', _user_label(change.made_by)),
        _fact('Requested at', change.made_at, 'datetime'),
    ))
    return [section] if section else []


def _display_value(value: Any) -> str:
    if isinstance(value, list):
        return ', '.join(str(x) for x in value)
    if isinstance(value, dict):
        return str(value)
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    return str(value)


def _settings_sections(change: PendingChange) -> list[dict]:
    proposed = change.proposed_values or {}
    original = change.original_values or {}
    keys = sorted(set(proposed) | set(original))
    facts = []
    for key in keys:
        label = key.replace('_', ' ').strip().title()
        before = original.get(key)
        after = proposed.get(key)
        if before is not None and before != '':
            facts.append(_fact(f'{label} (now)', _display_value(before)))
        if after is not None and after != '':
            facts.append(_fact(f'{label} (requested)', _display_value(after)))
    payload = change.apply_payload or {}
    if payload.get('module'):
        facts.insert(0, _fact('Module', payload.get('module')))
    section = _section('Settings change', facts=_facts(*facts))
    return [section] if section else []


def _role_sections(change: PendingChange, cache=None) -> list[dict]:
    from accounts.models import Permission, Role

    try:
        role_pk = int(change.entity_id)
        role = (cache.roles.get(role_pk) if cache else None) or Role.objects.filter(pk=role_pk).first()
    except (TypeError, ValueError):
        role = None
    proposed_ids = [
        int(x) for x in (
            (change.proposed_values or {}).get('permission_ids')
            or (change.apply_payload or {}).get('permission_ids')
            or []
        )
        if str(x).strip() != ''
    ]
    original_ids = [
        int(x) for x in ((change.original_values or {}).get('permission_ids') or [])
        if str(x).strip() != ''
    ]

    def _perms_for(ids):
        if not ids:
            return []
        if cache is not None:
            found = [cache.permissions[i] for i in ids if i in cache.permissions]
            if len(found) == len(set(ids)):
                return sorted(found, key=lambda p: (p.module, p.action))
        return list(
            Permission.objects.filter(id__in=ids).order_by('module', 'action')
        )

    proposed = _perms_for(proposed_ids)
    original = _perms_for(original_ids)

    def _perm_label(perm) -> str:
        return f'{perm.module}:{perm.action}'

    added = sorted({_perm_label(p) for p in proposed} - {_perm_label(p) for p in original})
    removed = sorted({_perm_label(p) for p in original} - {_perm_label(p) for p in proposed})
    section = _section('Role permissions', facts=_facts(
        _fact('Role', getattr(role, 'name', None) or change.entity_repr),
        _fact('Permissions now', len(original)),
        _fact('Permissions requested', len(proposed)),
        _fact('Added', ', '.join(added)) if added else None,
        _fact('Removed', ', '.join(removed)) if removed else None,
    ))
    return [section] if section else []


def pending_change_details(change: PendingChange, cache=None) -> dict | None:
    sections: list[dict] = []
    if change.action_type == ACTION_DEBT_COLLECTION:
        sections = _debt_collection_sections(change, cache=cache)
    elif change.action_type == ACTION_SALE_BACKFILL:
        sections = _backfill_sections(change, cache=cache)
    elif change.action_type in (
        ACTION_STOCK_ADJUST, ACTION_STOCK_PURCHASE, ACTION_STOCK_TRANSFER,
    ):
        sections = _stock_sections(change, cache=cache)
    elif change.action_type in (ACTION_CATEGORY_DEACTIVATE, ACTION_CATEGORY_DELETE):
        sections = _category_sections(change, cache=cache)
    elif change.action_type == ACTION_ROLE_PERMISSIONS:
        sections = _role_sections(change, cache=cache)
    elif change.action_type in (
        ACTION_STORE_SETTINGS, ACTION_PAYMENT_METHODS, ACTION_RECEIPT_LEGAL,
    ) or change.entity_type in (
        'settings.StoreSettings', 'settings.ModuleSetting',
    ):
        sections = _settings_sections(change)
    elif change.entity_type == 'sales.Sale':
        sale = _sale_for(change, cache=cache)
        if sale:
            payload = change.apply_payload if change.action_type == 'sale_complete' else None
            sections = sale_sections(sale, payment_payload=payload)
            if change.action_type == ACTION_SALE_REFUND:
                sections += _refund_sections(change, sale)
    elif change.entity_type in ('products.Product', 'products.ProductVariant'):
        sections = _product_sections(change, cache=cache)
    return {'sections': sections} if sections else None
