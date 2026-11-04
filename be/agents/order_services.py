"""
Field-order status machine and pack/assign orchestration.

Public entry points:
    - ``submit_order`` / ``start_packing`` / ``pack_order`` — through ready + sale
    - ``assign_delivery_agent`` / ``claim_ready_order`` — handoff to delivery
    - ``field_order_total`` / ``require_field_order_customer`` — pricing and customer

Side effects: ``pack_order`` sets ``stock_allocated``, creates ``sales.Sale`` via
``field_sale.record_field_sale``, and may enqueue a delivery stop. Assign calls
``delivery.services.enqueue_assigned_order``. Stock allocates on pack only.

Invariants: illegal transitions raise ``FieldOrderTransitionError``; dispatch assign
wins over driver self-claim on already-assigned ready orders.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from sales.models import Customer

from .config import MIN_SITE_MEDIA
from .models import FieldOrder


class FieldOrderTransitionError(ValidationError):
    """Illegal status transition, missing customer/lines, or pack precondition failure."""


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
    """
    Verify the order's site can be submitted (pin, customer, optional photos).

    Args:
        site: ``CustomerSite`` linked to the order; required non-null.
        min_media: Minimum photo count when > 0; default ``MIN_SITE_MEDIA``.

    Returns:
        None.

    Raises:
        FieldOrderTransitionError: Site missing, no pin, no customer, or too few photos.
    """
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
    """
    Sum line totals for a field order (quantity × unit_price per line).

    Args:
        order: Order whose ``lines`` relation is evaluated (may prefetch).

    Returns:
        Total in shop currency, quantized to 2 decimal places. Empty lines → ``0.00``.
    """
    total = Decimal('0.00')
    for line in order.lines.all():
        qty = line.quantity or Decimal('0')
        price = line.unit_price or Decimal('0')
        total += qty * price
    return total.quantize(Decimal('0.01'))


def require_field_order_customer(order: FieldOrder) -> Customer:
    """
    Ensure the order has a customer, copying from the site when needed.

    Args:
        order: Field order; may persist ``customer_id`` from ``order.site``.

    Returns:
        The linked ``Customer`` instance.

    Raises:
        FieldOrderTransitionError: No customer on order or site.

    Side effects:
        May ``save`` ``customer_id`` on the order when inferred from site.
    """
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
    """
    Move a field order to ``to_status`` if allowed by ``ALLOWED_TRANSITIONS``.

    Args:
        order: Current status read from the instance.
        to_status: Target status string (one of ``FieldOrder.STATUS_*``).

    Returns:
        Updated order with new ``status``.

    Raises:
        FieldOrderTransitionError: Transition not in the adjacency map.

    Side effects:
        Persists ``status`` and ``updated_at`` only.
    """
    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if to_status not in allowed:
        raise FieldOrderTransitionError({
            'status': f'Cannot move from {order.status} to {to_status}.',
        })
    order.status = to_status
    order.save(update_fields=['status', 'updated_at'])
    return order


def submit_order(order: FieldOrder) -> FieldOrder:
    """
    Submit a draft order for packing (draft → submitted).

    Args:
        order: Must be in ``STATUS_DRAFT`` with at least one line.

    Returns:
        Order in ``STATUS_SUBMITTED``.

    Raises:
        FieldOrderTransitionError: No lines, site not ready, or illegal status.
    """
    if not order.lines.exists():
        raise FieldOrderTransitionError({'lines': 'Add at least one line before submit.'})
    assert_site_ready_for_order(order.site)
    require_field_order_customer(order)
    return transition(order, FieldOrder.STATUS_SUBMITTED)


def start_packing(order: FieldOrder) -> FieldOrder:
    """
    Move submitted → packing without recording a sale.

    Args:
        order: Typically ``STATUS_SUBMITTED``.

    Returns:
        Order in ``STATUS_PACKING``.

    Raises:
        FieldOrderTransitionError: Illegal transition.
    """
    return transition(order, FieldOrder.STATUS_PACKING)


def pack_order(order: FieldOrder, user=None) -> FieldOrder:
    """
    Pack an order: allocate stock, create the field sale, mark ready.

    If status is ``submitted``, moves to ``packing`` first. Sets
    ``stock_allocated``, ``packed_at``, and ``STATUS_READY``, then calls
    ``record_field_sale`` inside one DB transaction.

    Args:
        order: Must reach ``STATUS_PACKING`` (auto from submitted).
        user: Acting user for sale attribution; falls back to ``created_by``.

    Returns:
        Order in ``STATUS_READY`` with ``sale`` linked when total > 0 debt path.

    Raises:
        FieldOrderTransitionError: Wrong status, customer missing, or stock/sale errors.

    Side effects:
        Stock movement, sale journal, customer debt for unpaid total; idempotent
        sale if ``order.sale_id`` already set inside ``record_field_sale``.
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
    """
    Assign a delivery agent and enqueue the order on today's route.

    Requires packed order (``STATUS_READY`` with ``stock_allocated``). Moves
    ready → ``out_for_delivery`` and calls ``delivery.services.enqueue_assigned_order``.

    Args:
        order: Packed field order.
        agent: User with ``delivery.update``; must be non-null.
        user: Optional actor for audit (defaults unused in service layer).

    Returns:
        Refreshed order after route enqueue.

    Raises:
        FieldOrderTransitionError: Unpacked order, wrong status, or missing agent.

    Side effects:
        Updates assignee timestamps; may create ``DeliveryStop`` on agent route.
    """
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
    Let a delivery agent self-assign an unassigned ready order.

    Dispatch assign always wins: orders with ``assigned_delivery_agent`` set
    cannot be claimed.

    Args:
        order: Must be ``STATUS_READY`` and unassigned.
        agent: Claiming user (passed through to ``assign_delivery_agent``).

    Returns:
        Same as ``assign_delivery_agent``.

    Raises:
        FieldOrderTransitionError: Not ready, already assigned, or missing agent.
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
    """
    Cancel a field order when the status graph allows cancelled.

    Args:
        order: Any non-terminal status that lists ``cancelled`` in transitions.

    Returns:
        Order in ``STATUS_CANCELLED``.

    Raises:
        FieldOrderTransitionError: Illegal transition (e.g. from ``done``).

    Side effects:
        Does not reverse stock or sale if already packed; cancel only updates status.
    """
    return transition(order, FieldOrder.STATUS_CANCELLED)
