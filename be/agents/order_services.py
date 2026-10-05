"""Field-order state machine. Stock: allocate on pack (see DECISIONS.md)."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from sales.models import Customer

from .config import MIN_SITE_MEDIA
from .models import FieldOrder


class FieldOrderTransitionError(ValidationError):
    """Illegal status transition or precondition failure."""


ALLOWED_TRANSITIONS = {
    FieldOrder.STATUS_DRAFT: {FieldOrder.STATUS_SUBMITTED, FieldOrder.STATUS_CANCELLED},
    FieldOrder.STATUS_SUBMITTED: {
        FieldOrder.STATUS_PACKING, FieldOrder.STATUS_CANCELLED,
    },
    FieldOrder.STATUS_PACKING: {
        FieldOrder.STATUS_READY, FieldOrder.STATUS_CANCELLED,
    },
    FieldOrder.STATUS_READY: {
        FieldOrder.STATUS_OUT_FOR_DELIVERY, FieldOrder.STATUS_CANCELLED,
    },
    FieldOrder.STATUS_OUT_FOR_DELIVERY: {
        FieldOrder.STATUS_DONE, FieldOrder.STATUS_CANCELLED,
    },
    FieldOrder.STATUS_DONE: set(),
    FieldOrder.STATUS_CANCELLED: set(),
}


def assert_site_ready_for_order(site, *, min_media: int = MIN_SITE_MEDIA) -> None:
    errors = {}
    if site is None:
        raise FieldOrderTransitionError({'site': 'Site is required.'})
    if not site.has_pin:
        errors['location'] = 'Site map pin is required before submit.'
    if min_media > 0 and site.media.count() < min_media:
        errors['media'] = f'At least {min_media} site photo(s) required.'
    if site.customer_id is None:
        errors['customer'] = 'Site must have a customer before submit.'
    if errors:
        raise FieldOrderTransitionError(errors)


def field_order_total(order: FieldOrder) -> Decimal:
    total = Decimal('0.00')
    for line in order.lines.all():
        qty = line.quantity or Decimal('0')
        price = line.unit_price or Decimal('0')
        total += qty * price
    return total.quantize(Decimal('0.01'))


def require_field_order_customer(order: FieldOrder) -> Customer:
    """Every field sale must be for a named customer."""
    if order.customer_id is None and order.site_id and order.site.customer_id:
        order.customer_id = order.site.customer_id
        order.save(update_fields=['customer', 'updated_at'])
        order.customer = order.site.customer
    if order.customer_id is None:
        raise FieldOrderTransitionError({
            'customer': 'Field sales require a customer.',
        })
    return order.customer


def transition(order: FieldOrder, to_status: str) -> FieldOrder:
    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if to_status not in allowed:
        raise FieldOrderTransitionError({
            'status': f'Cannot move from {order.status} to {to_status}.',
        })
    order.status = to_status
    order.save(update_fields=['status', 'updated_at'])
    return order


def submit_order(order: FieldOrder) -> FieldOrder:
    if not order.lines.exists():
        raise FieldOrderTransitionError({'lines': 'Add at least one line before submit.'})
    assert_site_ready_for_order(order.site)
    require_field_order_customer(order)
    return transition(order, FieldOrder.STATUS_SUBMITTED)


def start_packing(order: FieldOrder) -> FieldOrder:
    return transition(order, FieldOrder.STATUS_PACKING)


def pack_order(order: FieldOrder, user=None) -> FieldOrder:
    """
    Packing is when a field order becomes a sale: it is recorded for the agent
    who took the order, stock moves, the books post, and the unpaid total goes
    on the customer's debt (collected through debt management).
    """
    from .field_sale import record_field_sale

    if order.status == FieldOrder.STATUS_SUBMITTED:
        transition(order, FieldOrder.STATUS_PACKING)
        order.refresh_from_db()
    if order.status != FieldOrder.STATUS_PACKING:
        raise FieldOrderTransitionError({
            'status': f'Pack requires packing status (have {order.status}).',
        })
    require_field_order_customer(order)
    with transaction.atomic():
        order.stock_allocated = True
        order.packed_at = timezone.now()
        order.status = FieldOrder.STATUS_READY
        order.save(update_fields=[
            'stock_allocated', 'packed_at', 'status', 'updated_at',
        ])
        record_field_sale(order, user=user)
    return order


def assign_delivery_agent(order: FieldOrder, agent, user=None) -> FieldOrder:
    if agent is None:
        raise FieldOrderTransitionError({
            'delivery_agent_id': 'Delivery driver is required.',
        })
    packed = (
        order.status == FieldOrder.STATUS_READY
        and bool(order.stock_allocated)
    )
    if not packed:
        if order.status in (
            FieldOrder.STATUS_SUBMITTED,
            FieldOrder.STATUS_PACKING,
        ):
            raise FieldOrderTransitionError({
                'status': 'Pack the order before assigning a delivery driver.',
            })
        raise FieldOrderTransitionError({
            'status': f'Cannot assign from status {order.status}.',
        })
    order.assigned_delivery_agent = agent
    order.assigned_at = timezone.now()
    order.save(update_fields=[
        'assigned_delivery_agent', 'assigned_at', 'updated_at',
    ])
    # S09: put on today's delivery route as out_for_delivery.
    if order.status == FieldOrder.STATUS_READY:
        transition(order, FieldOrder.STATUS_OUT_FOR_DELIVERY)
        order.refresh_from_db()
    from delivery.services import enqueue_assigned_order
    enqueue_assigned_order(order)
    order.refresh_from_db()
    return order


def claim_ready_order(order: FieldOrder, agent) -> FieldOrder:
    """
    Delivery driver self-assign for unassigned ready orders.

    Dispatch assign always wins: already-assigned orders cannot be claimed.
    """
    if agent is None:
        raise FieldOrderTransitionError({
            'delivery_agent_id': 'Delivery driver is required.',
        })
    if order.status != FieldOrder.STATUS_READY:
        raise FieldOrderTransitionError({
            'status': f'Only ready orders can be claimed (have {order.status}).',
        })
    if order.assigned_delivery_agent_id is not None:
        raise FieldOrderTransitionError({
            'delivery_agent_id': (
                'Order already assigned. Dispatch assignment takes priority.'
            ),
        })
    return assign_delivery_agent(order, agent, user=agent)


def cancel_order(order: FieldOrder) -> FieldOrder:
    return transition(order, FieldOrder.STATUS_CANCELLED)
