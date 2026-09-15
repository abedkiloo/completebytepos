"""Shared inclusive date/datetime bounds for query filters."""

from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def inclusive_start_datetime(value):
    """Treat a date-only ``date_from`` as the first instant of that day."""
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
    """Treat a date-only ``date_to`` as the last instant of that day.

    HTML date inputs send ``YYYY-MM-DD``. Filtering ``created_at__lte`` that
    string matches midnight only, which hides every movement later that day
    and makes the ledger look frozen.
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
