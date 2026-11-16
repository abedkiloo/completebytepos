"""
Place each ward on a Monday–Friday call day.

The assignment unit is the ward. Every shop in that ward shares the day,
which is how sublocations are kept together: Kenya files a sublocation
under a ward, and this book does not store sublocation as its own field.
Wards that are close on the map, or in the same sub-county and not far
apart, grow onto a day that is already open.

Change the constants in this file to retune the book. Do not rewrite the
steps. A saved call-day plan row still beats this result.

Distance is the straight-line haversine in kilometres, not driving time.
"""

from __future__ import annotations

import math
import zlib

# Monday = 0 … Friday = 4. Do not set this above 5; the book has no weekend calls.
WEEKDAY_COUNT = 5
EARTH_RADIUS_KM = 6371.0
# A ward joins a day that already has a point at most this far away.
# Range 0–200. 0 turns neighbour joining off.
NEIGHBOR_KM = 12.0
# A ward joins a day that already holds its sub-county when the points
# are at most this far. Range 0–300. Set this equal to NEIGHBOR_KM to
# ignore the sub-county and use distance only.
SUB_COUNTY_KM = 25.0
# When two days are this close, the one with fewer customers wins.
# Range 0–50.
TIE_KM = 2.0
# Pins required before a ward has a map point. Range 1–10000.
MIN_PINS = 1
# Groups beyond this are ignored, heaviest first. Range 1–5000.
MAX_WARDS = 2000


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Straight-line distance between two WGS84 points.

    Args:
        lat1: Latitude of the first point, -90 through 90.
        lon1: Longitude of the first point, -180 through 180.
        lat2: Latitude of the second point, -90 through 90.
        lon2: Longitude of the second point, -180 through 180.

    Returns:
        float: Kilometres, 0 when the points are the same. No side effects.

    Raises:
        None. Values outside the ranges still return a number.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    chord = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    )
    return EARTH_RADIUS_KM * (2 * math.atan2(math.sqrt(chord), math.sqrt(1 - chord)))


def assign_ward_weekdays(groups: list[dict]) -> dict[tuple[str, str, str], int]:
    """
    Choose a weekday for each ward.

    Args:
        groups: One dict per ward. Keys ``county``, ``sub_county``, and
            ``ward`` are strings, blank allowed, compared case-insensitively.
            ``weight`` is the customer count, 0–100000. Zero is skipped.
            ``latitude`` and ``longitude`` are the ward point, or None when
            the ward has no usable pin. At most ``MAX_WARDS`` groups are
            used, heaviest first.

    Returns:
        dict: ``(county, sub_county, ward)`` in lower case to weekday 0–4.
        Empty when nothing has a positive weight. A ward with no point
        copies the day of its sub-county, then its county, then a stable
        hash. No writes.

    Raises:
        None. A pin that is not a number, or is outside -90–90 / -180–180,
        is treated as missing.
    """
    ranked = sorted(
        (group for group in groups if _weight(group) > 0),
        key=lambda group: (-_weight(group), _key(group)),
    )[:MAX_WARDS]
    placed = []
    unplaced = []
    for group in ranked:
        item = {
            'key': _key(group),
            'weight': _weight(group),
            'point': _point(group),
        }
        if not item['key'][0] or not item['key'][2]:
            continue
        if item['point'] is None:
            unplaced.append(item)
        else:
            placed.append(item)

    days: list[dict] = []
    for item in placed:
        _place(days, item)

    assigned: dict[tuple[str, str, str], int] = {}
    for day in days:
        for key in day['keys']:
            assigned[key] = day['weekday']
    for item in unplaced:
        assigned[item['key']] = _day_for_unplaced(days, item)
    return assigned


def _weight(group: dict) -> int:
    """
    Customer count for a ward, clamped.

    Args:
        group: Ward dict. Missing ``weight`` counts as 0.

    Returns:
        int: 0–100000.

    Raises:
        None.
    """
    try:
        value = int(group.get('weight') or 0)
    except (TypeError, ValueError):
        return 0
    if value < 0:
        return 0
    return min(value, 100000)


def _key(group: dict) -> tuple[str, str, str]:
    """
    Compare key for a ward.

    Args:
        group: Ward dict.

    Returns:
        tuple: Lowercased county, sub-county, and ward. Each part is 0–100
        characters. No side effects.
    """
    def part(name: str) -> str:
        return str(group.get(name) or '').strip().lower()[:100]

    return part('county'), part('sub_county'), part('ward')


def _point(group: dict):
    """
    Map point, or None when the pin is missing or out of range.

    Args:
        group: Ward dict with optional latitude and longitude.

    Returns:
        tuple or None: ``(lat, lon)`` inside -90–90 and -180–180.

    Raises:
        None.
    """
    try:
        lat = float(group.get('latitude'))
        lon = float(group.get('longitude'))
    except (TypeError, ValueError):
        return None
    if lat < -90 or lat > 90 or lon < -180 or lon > 180:
        return None
    return lat, lon


def _place(days: list[dict], item: dict) -> None:
    """
    Add a placed ward to an open day, or open the next weekday.

    Args:
        days: Days already opened. Mutated. Length 0–5.
        item: Ward with a point, a key, and a positive weight.

    Returns:
        None.

    Raises:
        None.
    """
    if not days:
        days.append(_open(0, item))
        return
    neighbor, distance = _closest(days, item, same_sub_county=False)
    if neighbor is not None and distance <= NEIGHBOR_KM:
        _join(neighbor, item)
        return
    sibling, sibling_distance = _closest(days, item, same_sub_county=True)
    if sibling is not None and sibling_distance <= SUB_COUNTY_KM:
        _join(sibling, item)
        return
    if len(days) < WEEKDAY_COUNT:
        days.append(_open(len(days), item))
        return
    _join(neighbor, item)


def _closest(days: list[dict], item: dict, *, same_sub_county: bool):
    """
    Nearest open day to a ward.

    Args:
        days: Open days. Each has ``points`` and ``subs``.
        item: Ward with a point and a key.
        same_sub_county: When True, only days that already contain this
            sub-county are considered.

    Returns:
        tuple: ``(day or None, distance in km)``. Distance is 0 when no
        day matches. No writes.

    Raises:
        None.
    """
    best = None
    best_distance = None
    sub = item['key'][1]
    for day in days:
        if same_sub_county and (not sub or sub not in day['subs']):
            continue
        distance = min(
            haversine_km(item['point'][0], item['point'][1], lat, lon)
            for lat, lon in day['points']
        )
        if _prefer(distance, day, best_distance, best):
            best = day
            best_distance = distance
    if best is None:
        return None, 0.0
    return best, best_distance


def _prefer(distance: float, day: dict, best_distance, best) -> bool:
    """
    Whether this day is a better home than the current best.

    Args:
        distance: Kilometres to this day, 0 or more.
        day: Candidate day.
        best_distance: Kilometres to the current best, or None.
        best: Current best day, or None.

    Returns:
        bool: True when this day should replace the best. A day more than
        ``TIE_KM`` closer wins. Inside the tie, the lighter day wins, then
        the earlier weekday.

    Raises:
        None.
    """
    if best is None or best_distance is None:
        return True
    if distance + TIE_KM < best_distance:
        return True
    if abs(distance - best_distance) > TIE_KM:
        return False
    if day['weight'] != best['weight']:
        return day['weight'] < best['weight']
    return day['weekday'] < best['weekday']


def _open(weekday: int, item: dict) -> dict:
    """
    Start a weekday with one ward.

    Args:
        weekday: 0–4.
        item: First ward on that day.

    Returns:
        dict: Mutable day record. Not saved.
    """
    day = {
        'weekday': weekday,
        'keys': [],
        'weight': 0,
        'points': [],
        'subs': set(),
        'counties': set(),
    }
    _join(day, item)
    return day


def _join(day: dict, item: dict) -> None:
    """
    Attach a ward to a day.

    Args:
        day: Day record from ``_open``.
        item: Ward dict.

    Returns:
        None. Mutates ``day`` only.
    """
    day['keys'].append(item['key'])
    day['weight'] += item['weight']
    day['subs'].add(item['key'][1])
    day['counties'].add(item['key'][0])
    if item['point'] is not None:
        day['points'].append(item['point'])


def _day_for_unplaced(days: list[dict], item: dict) -> int:
    """
    Day for a ward that has no map point.

    Args:
        days: Days already opened from pinned wards.
        item: Unplaced ward.

    Returns:
        int: 0–4. Copies the heaviest day in the same sub-county, then the
        heaviest day in the same county. When the county has no pinned
        ward, a stable hash of the ward name is used so the day does not
        change between requests.

    Raises:
        None.
    """
    sub = item['key'][1]
    county = item['key'][0]
    siblings = [
        day for day in days
        if sub and sub in day['subs'] and county in day['counties']
    ]
    if not siblings:
        siblings = [day for day in days if county in day['counties']]
    if siblings:
        chosen = max(siblings, key=lambda day: (day['weight'], -day['weekday']))
        chosen['weight'] += item['weight']
        chosen['subs'].add(sub)
        chosen['counties'].add(county)
        return chosen['weekday']
    raw = '|'.join(item['key']).encode('utf-8')
    return zlib.crc32(raw) % WEEKDAY_COUNT
