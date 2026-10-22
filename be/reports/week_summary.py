"""Calendar-week sales totals for the home dashboard (Monday–Sunday)."""

from datetime import date, datetime, timedelta

from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from sales.daily_sales import paid_debt_expression_sums


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
    from decimal import Decimal

    from django.db.models import DecimalField

    paid_expr, debt_expr = paid_debt_expression_sums()
    money = DecimalField(max_digits=14, decimal_places=2)
    zero = Value(Decimal('0.00'), output_field=money)
    # Keep Sum('total') separate — mixing it with paid/debt exprs aliasing F('total') fails.
    week_total = week_qs.aggregate(week_total=Sum('total'))['week_total'] or 0
    week_mix = week_qs.aggregate(
        paid_sum=Coalesce(Sum(paid_expr), zero),
        debt_sum=Coalesce(Sum(debt_expr), zero),
    )
    day_rows = (
        week_qs.annotate(day=TruncDate(at_field))
        .values('day')
        .annotate(
            sales_count=Count('id'),
            day_total=Sum('total'),
            paid_sum=Coalesce(Sum(paid_expr), zero),
            debt_sum=Coalesce(Sum(debt_expr), zero),
        )
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
                'total': float(row.get('day_total') or 0),
                'total_paid': float(row.get('paid_sum') or 0),
                'total_debt': float(row.get('debt_sum') or 0),
            }
        )
    return {
        'sales_count': week_qs.count(),
        'total': float(week_total),
        'total_paid': float(week_mix['paid_sum'] or 0),
        'total_debt': float(week_mix['debt_sum'] or 0),
        'days': days,
        'week_start': monday.isoformat(),
        'week_end': sunday.isoformat(),
    }
