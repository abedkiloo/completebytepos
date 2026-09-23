"""Delivery stop state machine + route sync."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from agents.models import FieldOrder
from agents.order_services import transition as fo_transition

from .config import REQUIRE_POD_TO_COMPLETE
from .models import (
    DeliveryLineResult,
    DeliveryRoute,
    DeliveryStop,
    ProofOfDelivery,
    ProposedPinCorrection,
)


class DeliveryTransitionError(ValidationError):
    """Illegal stop transition or precondition failure."""


ALLOWED_STOP_TRANSITIONS = {
    DeliveryStop.STATUS_PENDING: {
        DeliveryStop.STATUS_ARRIVED, DeliveryStop.STATUS_FAILED,
    },
    DeliveryStop.STATUS_ARRIVED: {
        DeliveryStop.STATUS_DELIVERING, DeliveryStop.STATUS_FAILED,
    },
    DeliveryStop.STATUS_DELIVERING: {
        DeliveryStop.STATUS_COLLECTED, DeliveryStop.STATUS_FAILED,
    },
    DeliveryStop.STATUS_COLLECTED: {
        DeliveryStop.STATUS_COMPLETED, DeliveryStop.STATUS_FAILED,
    },
    DeliveryStop.STATUS_COMPLETED: set(),
    DeliveryStop.STATUS_FAILED: set(),
}


def ensure_today_route(agent, route_date=None) -> DeliveryRoute:
    route_date = route_date or timezone.localdate()
    route, _ = DeliveryRoute.objects.get_or_create(
        route_date=route_date,
        delivery_agent=agent,
    )
    sync_assigned_orders_onto_route(route)
    return route


def sync_assigned_orders_onto_route(route: DeliveryRoute) -> DeliveryRoute:
    """Attach FieldOrders assigned to this agent that are out for delivery."""
    orders = FieldOrder.objects.filter(
        assigned_delivery_agent_id=route.delivery_agent_id,
        status=FieldOrder.STATUS_OUT_FOR_DELIVERY,
    ).filter(
        delivery_stop__isnull=True,
    ).order_by('assigned_at', 'id')
    next_seq = (
        route.stops.order_by('-sequence').values_list('sequence', flat=True).first() or 0
    )
    for order in orders:
        next_seq += 1
        create_stop_for_order(route, order, sequence=next_seq)
    return route


@transaction.atomic
def create_stop_for_order(route: DeliveryRoute, order: FieldOrder, *, sequence: int) -> DeliveryStop:
    stop = DeliveryStop.objects.create(
        route=route,
        field_order=order,
        sequence=sequence,
    )
    for line in order.lines.select_related('product'):
        DeliveryLineResult.objects.create(
            stop=stop,
            product=line.product,
            product_name=line.product_name or line.product.name,
            ordered_quantity=line.quantity,
            delivered_quantity=Decimal('0'),
            returned_quantity=Decimal('0'),
        )
    from .maps.geometry import invalidate_route_geometry
    invalidate_route_geometry(route)
    return stop


@transaction.atomic
def enqueue_assigned_order(order: FieldOrder) -> DeliveryStop:
    """Called after dispatch assign — move to out_for_delivery and add to today's route."""
    if order.assigned_delivery_agent_id is None:
        raise DeliveryTransitionError({
            'delivery_agent_id': 'Order must be assigned before enqueue.',
        })
    if order.status == FieldOrder.STATUS_READY:
        fo_transition(order, FieldOrder.STATUS_OUT_FOR_DELIVERY)
        order.refresh_from_db()
    elif order.status != FieldOrder.STATUS_OUT_FOR_DELIVERY:
        raise DeliveryTransitionError({
            'status': f'Cannot enqueue from status {order.status}.',
        })
    route = ensure_today_route(order.assigned_delivery_agent)
    existing = DeliveryStop.objects.filter(field_order=order).first()
    if existing:
        return existing
    next_seq = (
        route.stops.order_by('-sequence').values_list('sequence', flat=True).first() or 0
    ) + 1
    return create_stop_for_order(route, order, sequence=next_seq)


def transition_stop(stop: DeliveryStop, to_status: str) -> DeliveryStop:
    allowed = ALLOWED_STOP_TRANSITIONS.get(stop.status, set())
    if to_status not in allowed:
        raise DeliveryTransitionError({
            'status': f'Cannot move from {stop.status} to {to_status}.',
        })
    stop.status = to_status
    fields = ['status', 'updated_at']
    if to_status == DeliveryStop.STATUS_ARRIVED:
        stop.arrived_at = timezone.now()
        fields.append('arrived_at')
    if to_status == DeliveryStop.STATUS_COMPLETED:
        stop.completed_at = timezone.now()
        fields.append('completed_at')
    stop.save(update_fields=fields)
    return stop


def arrive(stop: DeliveryStop) -> DeliveryStop:
    return transition_stop(stop, DeliveryStop.STATUS_ARRIVED)


def start_delivery(stop: DeliveryStop) -> DeliveryStop:
    if stop.status == DeliveryStop.STATUS_PENDING:
        arrive(stop)
        stop.refresh_from_db()
    return transition_stop(stop, DeliveryStop.STATUS_DELIVERING)


def validate_line_quantities(
    ordered: Decimal, delivered: Decimal, returned: Decimal,
) -> None:
    if delivered < 0 or returned < 0:
        raise DeliveryTransitionError({
            'quantities': 'Quantities cannot be negative.',
        })
    if delivered + returned > ordered:
        raise DeliveryTransitionError({
            'quantities': 'Delivered + returned cannot exceed ordered quantity.',
        })


@transaction.atomic
def update_line_results(stop: DeliveryStop, lines_payload: list) -> DeliveryStop:
    if stop.status not in (
        DeliveryStop.STATUS_ARRIVED,
        DeliveryStop.STATUS_DELIVERING,
        DeliveryStop.STATUS_COLLECTED,
    ):
        if stop.status == DeliveryStop.STATUS_PENDING:
            start_delivery(stop)
            stop.refresh_from_db()
        else:
            raise DeliveryTransitionError({
                'status': f'Cannot update lines in status {stop.status}.',
            })
    if stop.status == DeliveryStop.STATUS_ARRIVED:
        transition_stop(stop, DeliveryStop.STATUS_DELIVERING)
        stop.refresh_from_db()

    for row in lines_payload:
        product_id = row.get('product_id')
        try:
            result = stop.line_results.get(product_id=product_id)
        except DeliveryLineResult.DoesNotExist as exc:
            raise DeliveryTransitionError({
                'product_id': f'Unknown product {product_id} on this stop.',
            }) from exc
        delivered = Decimal(str(row.get('delivered_quantity', result.delivered_quantity)))
        returned = Decimal(str(row.get('returned_quantity', result.returned_quantity)))
        validate_line_quantities(result.ordered_quantity, delivered, returned)
        result.delivered_quantity = delivered
        result.returned_quantity = returned
        # Stock policy stub: mark applied; real inventory ledger can hook later.
        result.stock_applied = True
        result.save(update_fields=[
            'delivered_quantity', 'returned_quantity', 'stock_applied',
        ])
    return stop


@transaction.atomic
def collect_money(
    stop: DeliveryStop,
    *,
    method: str,
    amount=None,
    notes: str = '',
) -> DeliveryStop:
    if stop.status not in (
        DeliveryStop.STATUS_DELIVERING,
        DeliveryStop.STATUS_COLLECTED,
    ):
        raise DeliveryTransitionError({
            'status': f'Collect requires delivering status (have {stop.status}).',
        })
    method = (method or '').strip().lower()
    if method not in ('cash', 'debt', 'defer_stk'):
        raise DeliveryTransitionError({
            'method': 'method must be cash, debt, or defer_stk.',
        })
    stop.collection_method = method
    stop.collection_amount = amount
    stop.collection_notes = notes or ''
    stop.status = DeliveryStop.STATUS_COLLECTED
    stop.save(update_fields=[
        'collection_method', 'collection_amount', 'collection_notes',
        'status', 'updated_at',
    ])
    return stop


@transaction.atomic
def save_pod(
    stop: DeliveryStop,
    *,
    signature_image=None,
    photo=None,
    notes: str = '',
    latitude=None,
    longitude=None,
    captured_at=None,
) -> ProofOfDelivery:
    captured_at = captured_at or timezone.now()
    pod, _ = ProofOfDelivery.objects.update_or_create(
        stop=stop,
        defaults={
            'notes': notes or '',
            'latitude': latitude,
            'longitude': longitude,
            'captured_at': captured_at,
        },
    )
    if signature_image is not None:
        pod.signature_image = signature_image
    if photo is not None:
        pod.photo = photo
    pod.save()
    return pod


@transaction.atomic
def complete_stop(stop: DeliveryStop, *, require_pod: bool | None = None) -> DeliveryStop:
    require_pod = REQUIRE_POD_TO_COMPLETE if require_pod is None else require_pod
    if stop.status != DeliveryStop.STATUS_COLLECTED:
        raise DeliveryTransitionError({
            'status': f'Complete requires collected status (have {stop.status}).',
        })
    if require_pod:
        try:
            pod = stop.pod
        except ProofOfDelivery.DoesNotExist as exc:
            raise DeliveryTransitionError({
                'pod': 'Proof of delivery is required before complete.',
            }) from exc
        if not pod.is_complete:
            raise DeliveryTransitionError({
                'pod': 'POD requires signature, photo, and lat/lng.',
            })
    transition_stop(stop, DeliveryStop.STATUS_COMPLETED)
    stop.refresh_from_db()
    order = stop.field_order
    if order.status == FieldOrder.STATUS_OUT_FOR_DELIVERY:
        fo_transition(order, FieldOrder.STATUS_DONE)
    return stop


def next_open_stop(route: DeliveryRoute) -> DeliveryStop | None:
    return (
        route.stops.exclude(
            status__in=(DeliveryStop.STATUS_COMPLETED, DeliveryStop.STATUS_FAILED),
        )
        .order_by('sequence', 'id')
        .first()
    )


def propose_pin_correction(
    stop: DeliveryStop,
    *,
    latitude,
    longitude,
    note: str = '',
    user=None,
) -> ProposedPinCorrection:
    return ProposedPinCorrection.objects.create(
        stop=stop,
        latitude=latitude,
        longitude=longitude,
        note=note or '',
        proposed_by=user,
    )
