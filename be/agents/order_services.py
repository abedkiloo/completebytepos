"""Field-order state machine. Stock: allocate on pack (see DECISIONS.md)."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from sales.models import Customer, CustomerWalletTransaction

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


def post_field_order_debt(order: FieldOrder, user=None) -> None:
    """
    When goods are packed/ready, the customer owes the order total.
    Collection then goes through normal debt collection (cash / M-Pesa).
    """
    customer = require_field_order_customer(order)
    amount = field_order_total(order)
    if amount <= 0:
        return
    reference = f'FO-{order.pk}'
    if CustomerWalletTransaction.objects.filter(
        customer=customer,
        source_type='debt',
        reference=reference,
    ).exists():
        return
    locked = Customer.objects.select_for_update().get(pk=customer.pk)
    locked.wallet_balance -= amount
    locked.save(update_fields=['wallet_balance', 'updated_at'])
    CustomerWalletTransaction.objects.create(
        customer=locked,
        transaction_type='debit',
        source_type='debt',
        amount=amount,
        balance_after=locked.wallet_balance,
        reference=reference,
        notes=(
            f'Field order #{order.pk} packed — unpaid balance added as customer debt'
        ),
        created_by=user or order.created_by,
    )
    order.customer = locked


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
    Allocate-on-pack: mark stock_allocated without inventing a second inventory ledger.
    Real stock movements can hook here later; S08 records the policy decision.
    Packed field sales post customer debt so cash is collected through debt management.
    """
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
        post_field_order_debt(order, user=user)
    return order


def assign_delivery_agent(order: FieldOrder, agent) -> FieldOrder:
    if agent is None:
        raise FieldOrderTransitionError({
            'delivery_agent_id': 'Delivery driver is required.',
        })
    if order.status not in (
        FieldOrder.STATUS_READY,
        FieldOrder.STATUS_PACKING,
    ):
        # Allow assign from ready; if still packing, pack first.
        if order.status == FieldOrder.STATUS_SUBMITTED:
            raise FieldOrderTransitionError({
                'status': 'Pack the order before assigning a delivery driver.',
            })
        raise FieldOrderTransitionError({
            'status': f'Cannot assign from status {order.status}.',
        })
    if order.status == FieldOrder.STATUS_PACKING and not order.stock_allocated:
        pack_order(order)
        order.refresh_from_db()
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
    return assign_delivery_agent(order, agent)


def cancel_order(order: FieldOrder) -> FieldOrder:
    return transition(order, FieldOrder.STATUS_CANCELLED)
