"""Google Routes API — called from Django only, never from the phone or browser."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

ROUTES_URL = 'https://routes.googleapis.com/directions/v2:computeRoutes'
FIELD_MASK = 'routes.polyline.encodedPolyline'


def post_json(url: str, payload: dict, headers: dict, timeout: float = 8):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _lat_lng(point) -> dict:
    lat, lng = point
    return {'latitude': float(lat), 'longitude': float(lng)}


def routes_request_body(origin, destination, intermediates=None) -> dict:
    body = {
        'origin': {'location': {'latLng': _lat_lng(origin)}},
        'destination': {'location': {'latLng': _lat_lng(destination)}},
        'travelMode': 'DRIVE',
        'polylineEncoding': 'ENCODED_POLYLINE',
        'polylineQuality': 'OVERVIEW',
    }
    if intermediates:
        body['intermediates'] = [
            {'location': {'latLng': _lat_lng(point)}} for point in intermediates
        ]
    return body


def fetch_encoded_polyline(points, *, api_key: str, post=post_json) -> str | None:
    """
    Drive polyline for origin → waypoints → destination.
    `points` must have at least two (lat, lng) pairs. Returns None on any failure.
    """
    if not api_key or len(points) < 2:
        return None
    origin = points[0]
    destination = points[-1]
    intermediates = points[1:-1] if len(points) > 2 else []
    try:
        data = post(
            ROUTES_URL,
            routes_request_body(origin, destination, intermediates),
            {
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': api_key,
                'X-Goog-FieldMask': FIELD_MASK,
            },
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return None
    routes = data.get('routes') if isinstance(data, dict) else None
    if not routes:
        return None
    polyline = (routes[0] or {}).get('polyline') or {}
    encoded = polyline.get('encodedPolyline') or ''
    return encoded or None
