"""
Place each sub-county on a Monday–Friday call day.

Every shop in one sub-county is phoned on the same day. Sub-counties are
sorted by county, then by sub-county name, and handed out in turn:
Monday, Tuesday, Wednesday, Thursday, Friday, then Monday again.

A saved call-day plan row still beats this result. Change ``WEEKDAY_COUNT``
only if the book gains or loses a weekday. Do not put Saturday or Sunday
in the rotation.
"""

from __future__ import annotations

# Monday = 0 … Friday = 4.
WEEKDAY_COUNT = 5
# Sub-counties kept, alphabetical. Kenya has well under this. Range 1–5000.
MAX_SUB_COUNTIES = 2000


def assign_sub_county_weekdays(groups: list[dict]) -> dict[tuple[str, str], int]:
    """
    Give each sub-county one weekday by round robin.

    Args:
        groups: One dict per sub-county. ``county`` and ``sub_county`` are
            strings, blank allowed, compared case-insensitively and trimmed
            to 100 characters. ``weight`` is the customer count, 0–100000.
            Zero is skipped. At most ``MAX_SUB_COUNTIES`` groups are used.

    Returns:
        dict: ``(county, sub_county)`` in lower case to weekday 0–4.
        The first name in alphabetical order is Monday. Each following
        sub-county takes the next weekday, and the sixth returns to Monday.
        Empty when every weight is 0. No writes.

    Raises:
        None. A weight that is not a number is skipped.
    """
    ranked = sorted(
        (group for group in groups if _weight(group) > 0),
        key=_key,
    )[:MAX_SUB_COUNTIES]
    assigned: dict[tuple[str, str], int] = {}
    for index, group in enumerate(ranked):
        assigned[_key(group)] = index % WEEKDAY_COUNT
    return assigned


def _weight(group: dict) -> int:
    """
    Customer count for a sub-county, clamped.

    Args:
        group: Sub-county dict. Missing ``weight`` counts as 0.

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


def _key(group: dict) -> tuple[str, str]:
    """
    Compare key for a sub-county.

    Args:
        group: Sub-county dict.

    Returns:
        tuple: Lowercased county and sub-county. Each part is 0–100
        characters. No side effects.
    """
    def part(name: str) -> str:
        return str(group.get(name) or '').strip().lower()[:100]

    return part('county'), part('sub_county')
