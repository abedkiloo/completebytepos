"""
Shared inclusive date/datetime bounds for query filters.

Public entry points:
    - ``inclusive_start_datetime`` — expand date-only ``date_from`` to day start
    - ``inclusive_end_datetime`` — expand date-only ``date_to`` to day end

Uses ``timezone.get_current_timezone()`` for naive inputs. Date-only strings
must be exactly 10 characters (``YYYY-MM-DD``) to avoid midnight end truncation.
"""

from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def inclusive_start_datetime(value):
    """
    Treat a date-only ``date_from`` as the first instant of that day.

    Args:
        value: ISO date (10 chars), ISO datetime string, aware/naive datetime,
            or empty/``None``.

    Returns:
        Timezone-aware ``datetime`` at local start-of-day for date-only input;
        aware datetime for parseable datetimes; ``None`` when empty; unchanged
        ``value`` when parsing fails for non-10-char strings.
    """
    if value in (None, ''):
        return None
    text = str(value).strip()
    if len(text) == 10:
        parsed_d = parse_date(text)
        if parsed_d is not None:
            start = datetime.combine(parsed_d, time.min)
            if timezone.is_naive(start):
                return timezone.make_aware(start, timezone.get_current_timezone())
            return start
    parsed_dt = parse_datetime(text)
    if parsed_dt is not None:
        if timezone.is_naive(parsed_dt):
            return timezone.make_aware(parsed_dt, timezone.get_current_timezone())
        return parsed_dt
    return value


def inclusive_end_datetime(value):
    """
    Treat a date-only ``date_to`` as the last instant of that day.

    HTML date inputs send ``YYYY-MM-DD``. Filtering ``created_at__lte`` that
    string matches midnight only, which hides every movement later that day
    and makes the ledger look frozen.

    Args:
        value: Same shapes as ``inclusive_start_datetime``.

    Returns:
        Timezone-aware ``datetime`` at local ``time.max`` for date-only input;
        aware datetime for full timestamps; ``None`` when empty; passthrough when
        unparsed.
    """
    if value in (None, ''):
        return None
    text = str(value).strip()
    # Date-only (HTML ``<input type="date">``). Do not let parse_datetime
    # coerce this to midnight — that would exclude the rest of the day.
    if len(text) == 10:
        parsed_d = parse_date(text)
        if parsed_d is not None:
            end = datetime.combine(parsed_d, time.max)
            if timezone.is_naive(end):
                return timezone.make_aware(end, timezone.get_current_timezone())
            return end
    parsed_dt = parse_datetime(text)
    if parsed_dt is not None:
        if timezone.is_naive(parsed_dt):
            return timezone.make_aware(parsed_dt, timezone.get_current_timezone())
        return parsed_dt
    return value
