"""Last-7-days sales totals for the home dashboard."""

from datetime import datetime, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone


def coerce_day_key(value):
    """Normalize TruncDate output to ``datetime.date`` (some DBs return datetime)."""
    if value is None:
        return None
    to_date = getattr(value, 'date', None)
    if callable(to_date):
        return to_date()
    return value


def week_sales_summary(completed_sales, at_field='occurred_at'):
    """Last 7 days including today: totals plus per-day rows."""
    today = timezone.now().date()
    start = timezone.make_aware(datetime.combine(today - timedelta(days=6), datetime.min.time()))
    week_qs = completed_sales.filter(**{f'{at_field}__gte': start})
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
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
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
    }
