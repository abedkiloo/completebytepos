"""Calendar-week sales totals for the home dashboard (Monday–Sunday)."""

from datetime import date, datetime, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone


def monday_of_week(day: date | None = None) -> date:
    """Return the Monday that starts the ISO week containing ``day`` (local)."""
    day = day or timezone.localdate()
    # Monday = 0 … Sunday = 6
    return day - timedelta(days=day.weekday())


def week_bounds(day: date | None = None) -> tuple[date, date]:
    """Monday and Sunday of the calendar week containing ``day``."""
    monday = monday_of_week(day)
    return monday, monday + timedelta(days=6)


def coerce_day_key(value):
    """Normalize TruncDate output to ``datetime.date`` (some DBs return datetime)."""
    if value is None:
        return None
    to_date = getattr(value, 'date', None)
    if callable(to_date):
        return to_date()
    return value


def week_sales_summary(completed_sales, at_field='occurred_at'):
    """
    Current calendar week (Mon–Sun): totals plus one row per weekday.

    Future days in the week are included with zero totals so the chart always
    shows Monday through Sunday.
    """
    today = timezone.localdate()
    monday, sunday = week_bounds(today)
    start = timezone.make_aware(datetime.combine(monday, datetime.min.time()))
    # Cap at end of today so future-dated rows do not inflate "this week".
    end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    week_qs = completed_sales.filter(
        **{f'{at_field}__gte': start, f'{at_field}__lte': end},
    )
    week_total = week_qs.aggregate(total=Sum('total'))['total'] or 0
    day_rows = (
        week_qs.annotate(day=TruncDate(at_field))
        .values('day')
        .annotate(sales_count=Count('id'), total=Sum('total'))
    )
    by_day = {}
    for row in day_rows:
        by_day[coerce_day_key(row['day'])] = row
    days = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        row = by_day.get(day) or {}
        days.append(
            {
                'date': day.isoformat(),
                'label': day.strftime('%a'),
                'sales_count': int(row.get('sales_count') or 0),
                'total': float(row.get('total') or 0),
            }
        )
    return {
        'sales_count': week_qs.count(),
        'total': float(week_total),
        'days': days,
        'week_start': monday.isoformat(),
        'week_end': sunday.isoformat(),
    }
