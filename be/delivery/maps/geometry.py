"""Build and cache planned-route geometry. Live GPS is out of scope."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils import timezone

from settings.models import Branch
from settings.utils import get_current_branch

from .config import (
    DEFAULT_DEPOT_LABEL,
    DEFAULT_DEPOT_LATITUDE,
    DEFAULT_DEPOT_LONGITUDE,
    maps_server_key,
)
from .google_routes import fetch_encoded_polyline
from .polyline import decode_polyline, encode_polyline

SOURCE_STRAIGHT = 'straight'
SOURCE_GOOGLE = 'google'


def _coord(value) -> float | None:
    if value is None or value == '':
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def resolve_depot(request=None) -> dict:
    """Branch lat/lng, or Nairobi fallback until the shop pin is saved."""
    branch = None
    if request is not None:
        branch = get_current_branch(request)
    if branch is None:
        branch = Branch.objects.filter(is_headquarters=True, is_active=True).first()
    if branch is None:
        branch = Branch.objects.filter(is_active=True).order_by('id').first()
    if branch is None:
        return {
            'latitude': DEFAULT_DEPOT_LATITUDE,
            'longitude': DEFAULT_DEPOT_LONGITUDE,
            'label': DEFAULT_DEPOT_LABEL,
            'placeholder': True,
            'branch_id': None,
        }
    lat = _coord(branch.latitude)
    lng = _coord(branch.longitude)
    placeholder = lat is None or lng is None
    return {
        'latitude': DEFAULT_DEPOT_LATITUDE if placeholder else lat,
        'longitude': DEFAULT_DEPOT_LONGITUDE if placeholder else lng,
        'label': branch.name or DEFAULT_DEPOT_LABEL,
        'placeholder': placeholder,
        'branch_id': branch.id,
    }


def geometry_fingerprint(depot: dict, stop_points: list, *, routes_configured: bool = False) -> str:
    parts = [
        f"{float(depot['latitude']):.5f},{float(depot['longitude']):.5f}",
        f"ph={1 if depot.get('placeholder') else 0}",
        f"r={1 if routes_configured else 0}",
    ]
    for stop_id, lat, lng in stop_points:
        parts.append(f'{stop_id}:{float(lat):.5f},{float(lng):.5f}')
    return '|'.join(parts)


def invalidate_route_geometry(route) -> None:
    route.encoded_polyline = ''
    route.polyline_source = ''
    route.geometry_fingerprint = ''
    route.geometry_updated_at = None
    route.save(
        update_fields=[
            'encoded_polyline',
            'polyline_source',
            'geometry_fingerprint',
            'geometry_updated_at',
            'updated_at',
        ],
    )


def _stop_rows(route) -> list[dict]:
    rows = []
    stops = route.stops.select_related('field_order__site', 'field_order__customer').order_by(
        'sequence', 'id',
    )
    for stop in stops:
        site = getattr(stop.field_order, 'site', None)
        customer = getattr(stop.field_order, 'customer', None)
        lat = _coord(getattr(site, 'latitude', None)) if site else None
        lng = _coord(getattr(site, 'longitude', None)) if site else None
        label = ''
        if site is not None:
            label = (site.label or '').strip()
        if not label and customer is not None:
            label = (customer.name or '').strip()
        rows.append({
            'id': stop.id,
            'sequence': stop.sequence,
            'status': stop.status,
            'label': label or f'Stop {stop.sequence}',
            'latitude': lat,
            'longitude': lng,
        })
    return rows


def _waypoints(depot: dict, stop_rows: list) -> list[tuple[int | None, float, float]]:
    points = [(None, float(depot['latitude']), float(depot['longitude']))]
    for row in stop_rows:
        if row['latitude'] is None or row['longitude'] is None:
            continue
        points.append((row['id'], float(row['latitude']), float(row['longitude'])))
    return points


def _refresh_polyline(route, fingerprint: str, waypoints: list[tuple[float, float]]) -> None:
    encoded = ''
    source = ''
    if len(waypoints) >= 2:
        key = maps_server_key()
        if key:
            encoded = fetch_encoded_polyline(waypoints, api_key=key) or ''
            if encoded:
                source = SOURCE_GOOGLE
        if not encoded:
            encoded = encode_polyline(waypoints)
            source = SOURCE_STRAIGHT
    route.encoded_polyline = encoded
    route.polyline_source = source
    route.geometry_fingerprint = fingerprint
    route.geometry_updated_at = timezone.now()
    route.save(
        update_fields=[
            'encoded_polyline',
            'polyline_source',
            'geometry_fingerprint',
            'geometry_updated_at',
            'updated_at',
        ],
    )


def _should_rebuild(route, fingerprint: str, waypoint_count: int) -> bool:
    if route.geometry_fingerprint != fingerprint:
        return True
    if waypoint_count >= 2 and not route.encoded_polyline:
        return True
    return False


def _agent_name(user) -> str:
    if user is None:
        return ''
    full = (user.get_full_name() or '').strip()
    return full or user.username


def empty_geometry(agent_id, route_date, request=None, agent=None) -> dict:
    depot = resolve_depot(request)
    return {
        'route_id': None,
        'route_date': str(route_date),
        'delivery_agent_id': agent_id,
        'delivery_agent_name': _agent_name(agent),
        'depot': depot,
        'encoded_polyline': '',
        'source': '',
        'path': [
            {'latitude': depot['latitude'], 'longitude': depot['longitude']},
        ],
        'stops': [],
    }


def build_route_geometry(route, request=None) -> dict:
    depot = resolve_depot(request)
    stop_rows = _stop_rows(route)
    pinned = [
        (row['id'], row['latitude'], row['longitude'])
        for row in stop_rows
        if row['latitude'] is not None and row['longitude'] is not None
    ]
    fingerprint = geometry_fingerprint(
        depot, pinned, routes_configured=bool(maps_server_key()),
    )
    waypoints = [(lat, lng) for _, lat, lng in _waypoints(depot, stop_rows)]
    if _should_rebuild(route, fingerprint, len(waypoints)):
        _refresh_polyline(route, fingerprint, waypoints)

    encoded = route.encoded_polyline or ''
    path_points = decode_polyline(encoded) if encoded else waypoints
    if not path_points:
        path_points = waypoints[:1] if waypoints else [
            (float(depot['latitude']), float(depot['longitude'])),
        ]

    return {
        'route_id': route.id,
        'route_date': str(route.route_date),
        'delivery_agent_id': route.delivery_agent_id,
        'delivery_agent_name': _agent_name(route.delivery_agent),
        'depot': depot,
        'encoded_polyline': encoded,
        'source': route.polyline_source or '',
        'path': [
            {'latitude': lat, 'longitude': lng} for lat, lng in path_points
        ],
        'stops': stop_rows,
    }
