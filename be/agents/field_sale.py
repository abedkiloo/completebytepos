"""Turn a packed field order into a real sale credited to the agent who took it.

The sale moves stock, posts to the books and puts the unpaid total on the
customer's debt, exactly like a shop credit sale. It is marked
``entry_source='field'`` so every screen can tell field sales from shop sales.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import FieldOrder
from .order_services import FieldOrderTransitionError, require_field_order_customer

FIELD_ENTRY_SOURCE = 'field'


def _field_sale_items(order: FieldOrder) -> list[dict]:
    from products.stock_utils import sellable_unit_cost
    from settings.feature_flags import is_product_variants_enabled

    variants_on = is_product_variants_enabled()
    items = []
    for line in order.lines.select_related('product', 'variant'):
        qty = Decimal(str(line.quantity or 0))
        label = line.product_name or line.product.name
        if qty <= 0 or qty != qty.to_integral_value():
            raise FieldOrderTransitionError({
                'lines': f'{label}: quantity must be a whole number to record the sale.',
            })
        quantity = int(qty)
        variant = line.variant if variants_on else None
        unit_price = Decimal(str(line.unit_price or 0))
        items.append({
            'product': line.product,
            'variant': variant,
            'quantity': quantity,
            'unit_price': unit_price,
            'unit_cost': sellable_unit_cost(line.product, variant),
            'subtotal': unit_price * quantity,
        })
    if not items:
        raise FieldOrderTransitionError({'lines': 'Add at least one line before packing.'})
    return items


def record_field_sale(order: FieldOrder, user=None, *, move_stock: bool = True, post_debt: bool = True):
    """Create (once) the sale for a packed field order and link it to the order."""
    from sales.services import SaleService

    if order.sale_id:
        return order.sale

    customer = require_field_order_customer(order)
    agent = order.created_by or user
    items = _field_sale_items(order)
    service = SaleService()
    try:
        with transaction.atomic():
            sale = service.create_sale(
                {
                    'sale_type': 'pos',
                    'payment_method': 'other',
                    'amount_paid': Decimal('0'),
                    'customer': customer,
                    'served_by': agent,
                    'entry_source': FIELD_ENTRY_SOURCE,
                    'client_channel': 'mobile',
                    'occurred_at': order.packed_at,
                    'notes': f'Field order #{order.pk}',
                },
                [],
                user=agent,
                validated_items=items,
                complete=move_stock,
            )
            if not move_stock:
                sale.status = 'completed'
                sale.save(update_fields=['status', 'updated_at'])
                from accounting.services import create_sale_journal_entry

                create_sale_journal_entry(sale)
            if post_debt and sale.total > 0:
                service._apply_sale_payment(
                    customer,
                    sale,
                    agent,
                    {
                        'wallet_amount_used': Decimal('0'),
                        'wallet_credit_added': Decimal('0'),
                        'change': Decimal('0'),
                        'pending_debt': sale.total,
                        'amount_paid_recorded': Decimal('0'),
                    },
                )
            order.sale = sale
            order.save(update_fields=['sale', 'updated_at'])
    except ValidationError as exc:
        raise FieldOrderTransitionError({'stock': ' '.join(exc.messages)}) from exc
    return sale
