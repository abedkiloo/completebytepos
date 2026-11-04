"""
Delivery stop state machine, route sync, POD, and collection.

Public entry points:
    - ``ensure_today_route`` / ``enqueue_assigned_order`` — route + stop creation
    - ``update_line_results`` / ``collect_money`` / ``save_pod`` / ``complete_stop``
    - ``propose_pin_correction`` — pending site pin fixes

Side effects: creates ``DeliveryStop`` / ``DeliveryLineResult`` rows; invalidates
route geometry; may transition linked ``FieldOrder`` to ``done`` on complete.
Stock return policy on line results sets ``stock_applied`` (ledger hook TBD).

Invariants: stop status graph in ``ALLOWED_STOP_TRANSITIONS``; delivered + returned
≤ ordered quantity per line.
"""

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
    """Illegal stop transition, quantity violation, or POD/collection precondition failure."""


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
    """
    Get or create the agent's route for a day and sync assigned orders onto it.

    Args:
        agent: Delivery assignee (route owner).
        route_date: Calendar date in local timezone; defaults to today.

    Returns:
        ``DeliveryRoute`` with stops synced for out-for-delivery unlinked orders.

    Side effects:
        May create route row and additional ``DeliveryStop`` rows via sync.
    """
    route_date = route_date or timezone.localdate()
    route, _ = DeliveryRoute.objects.get_or_create(
        route_date=route_date,
        delivery_agent=agent,
    )
    sync_assigned_orders_onto_route(route)
    return route


def sync_assigned_orders_onto_route(route: DeliveryRoute) -> DeliveryRoute:
    """
    Attach out-for-delivery field orders missing a stop onto ``route``.

    Args:
        route: Target route for ``route.delivery_agent``.

    Returns:
        Same route after append-only stop creation (ordered by ``assigned_at``).

    Side effects:
        Creates stops + line results; invalidates route geometry per stop.
    """
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
    """
    Create one stop and line-result rows mirroring the field order lines.

    Args:
        route: Parent route (must match order assignee when called from enqueue).
        order: ``FieldOrder`` with lines; one stop per order (callers check duplicates).
        sequence: Sort key on route; typically monotonic increasing ≥ 1.

    Returns:
        New ``DeliveryStop`` in ``STATUS_PENDING``.

    Side effects:
        Inserts ``DeliveryLineResult`` per order line; invalidates route geometry.
    """
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
    """
    After assign: ensure out-for-delivery and append stop on assignee's today route.

    Args:
        order: Must have ``assigned_delivery_agent``; ready or out_for_delivery.

    Returns:
        Existing or newly created ``DeliveryStop`` for the order.

    Raises:
        DeliveryTransitionError: Missing assignee or illegal field order status.

    Side effects:
        May FO-transition ready → out_for_delivery; creates route/stop rows.
    """
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
    """
    Move a stop along ``ALLOWED_STOP_TRANSITIONS``.

    Args:
        stop: Current stop instance.
        to_status: Target ``DeliveryStop.STATUS_*`` value.

    Returns:
        Updated stop; sets ``arrived_at`` on arrive, ``completed_at`` on complete.

    Raises:
        DeliveryTransitionError: Disallowed edge in the graph.
    """
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
    """Transition pending → arrived and stamp ``arrived_at``."""
    return transition_stop(stop, DeliveryStop.STATUS_ARRIVED)


def start_delivery(stop: DeliveryStop) -> DeliveryStop:
    """
    Begin delivery at a stop (pending → arrived → delivering if needed).

    Args:
        stop: Stop in pending or arrived state.

    Returns:
        Stop in ``STATUS_DELIVERING``.

    Raises:
        DeliveryTransitionError: Illegal transition from current status.
    """
    if stop.status == DeliveryStop.STATUS_PENDING:
        arrive(stop)
        stop.refresh_from_db()
    return transition_stop(stop, DeliveryStop.STATUS_DELIVERING)


def validate_line_quantities(
    ordered: Decimal, delivered: Decimal, returned: Decimal,
) -> None:
    """
    Validate delivered/returned quantities against ordered amount.

    Args:
        ordered: Original line quantity (≥ 0).
        delivered: Units handed to customer; must be ≥ 0.
        returned: Units brought back; must be ≥ 0.

    Returns:
        None.

    Raises:
        DeliveryTransitionError: Negative qty or ``delivered + returned > ordered``.
    """
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
    """
    Update per-product delivered/returned quantities on a stop.

    Auto-starts delivery when still pending. Each payload row needs ``product_id``;
    omitted quantities keep existing values.

    Args:
        stop: Stop in arrived, delivering, or collected (or pending → auto advance).
        lines_payload: Non-empty list of dicts with ``product_id`` and optional
            ``delivered_quantity`` / ``returned_quantity``.

    Returns:
        Refreshed stop after line saves.

    Raises:
        DeliveryTransitionError: Wrong status, unknown product on stop, or qty rules.

    Side effects:
        Sets ``stock_applied=True`` on each touched line result.
    """
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
    """
    Record collection method/amount and move stop to collected.

    Args:
        stop: Must be ``delivering`` or already ``collected`` (idempotent fields).
        method: ``cash``, ``debt``, or ``defer_stk`` (case-insensitive).
        amount: Optional ``Decimal`` money (2 dp); may be null for defer.
        notes: Free-text collection notes stored on the stop.

    Returns:
        Stop in ``STATUS_COLLECTED``.

    Raises:
        DeliveryTransitionError: Wrong status or invalid method string.
    """
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
    """
    Create or update proof-of-delivery media and metadata for a stop.

    Args:
        stop: Target delivery stop (one POD per stop).
        signature_image: Optional uploaded signature file; preserved when omitted.
        photo: Optional delivery photo file; preserved when omitted.
        notes: POD notes (may be empty).
        latitude: GPS latitude (7 dp) or None.
        longitude: GPS longitude (7 dp) or None.
        captured_at: Event time; defaults to now (timezone-aware).

    Returns:
        Saved ``ProofOfDelivery`` instance.

    Side effects:
        Writes image files to ``delivery_pod/`` when provided.
    """
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
    """
    Finish a stop after collection (and optional complete POD).

    Args:
        stop: Must be ``STATUS_COLLECTED``.
        require_pod: When True (default from ``REQUIRE_POD_TO_COMPLETE``), POD must
            exist and ``pod.is_complete``. Pass False to bypass in tests.

    Returns:
        Stop in ``STATUS_COMPLETED``.

    Raises:
        DeliveryTransitionError: Not collected, missing POD, or incomplete POD.

    Side effects:
        Marks field order ``done`` when still ``out_for_delivery``.
    """
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
    """
    Return the first non-terminal stop on a route by sequence.

    Args:
        route: Route whose ``stops`` are considered.

    Returns:
        Next stop not in ``completed`` or ``failed``, or ``None`` when all done.
    """
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
    """
    Record a pending pin correction for manager review (no site overwrite).

    Args:
        stop: Delivery stop whose site pin may be wrong.
        latitude: Proposed latitude (required, 7 dp field).
        longitude: Proposed longitude (required, 7 dp field).
        note: Driver explanation (optional).
        user: Proposer stored on ``proposed_by``.

    Returns:
        New ``ProposedPinCorrection`` in ``STATUS_PENDING``.

    Side effects:
        Inserts correction row only; does not mutate ``CustomerSite`` coordinates.
    """
    return ProposedPinCorrection.objects.create(
        stop=stop,
        latitude=latitude,
        longitude=longitude,
        note=note or '',
        proposed_by=user,
    )
