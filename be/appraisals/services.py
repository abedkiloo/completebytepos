"""Build appraisal progress snapshots from posted sales."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from accounts.models import UserProfile
from reports.sale_scope import posted_sales
from sales.models import SaleRefund

from .engine import (
    daily_star,
    greeting_copy,
    is_four_star_month,
    monthly_average,
    monthly_bonus,
    star_tone,
    year_end_result,
)
from .policy import load_template, public_policy, show_on_home, template_for_role, is_skipped_appraisal_role
from .tips import pick_daily_tips


def _aware(dt: datetime) -> datetime:
    if timezone.is_naive(dt) and timezone.is_aware(timezone.now()):
        return timezone.make_aware(dt)
    return dt


def _year_bounds(year: int) -> tuple[datetime, datetime]:
    return _aware(datetime(year, 1, 1)), _aware(datetime(year + 1, 1, 1))


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = _aware(datetime(year, month, 1))
    if month == 12:
        end = _aware(datetime(year + 1, 1, 1))
    else:
        end = _aware(datetime(year, month + 1, 1))
    return start, end


def _staff_q(user_id: int) -> Q:
    return Q(served_by_id=user_id) | Q(served_by__isnull=True, cashier_id=user_id)


def _display_name(user: User | None) -> str:
    if user is None:
        return 'Unassigned'
    full = user.get_full_name().strip()
    return full or user.username


_LEGACY_ROLE_NAMES = {
    'manager': 'Manager',
    'cashier': 'Sales Personnel',
    'admin': 'Super Admin',
    'super_admin': 'Super Admin',
}


def staff_role_name(user: User | None) -> str:
    if user is None:
        return 'Sales Personnel'
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return 'Sales Personnel'
    custom = getattr(profile, 'custom_role', None)
    custom_name = str(getattr(custom, 'name', '') or '').strip()
    if custom_name:
        return custom_name
    legacy = (getattr(profile, 'role', None) or '').lower()
    return _LEGACY_ROLE_NAMES.get(legacy, 'Sales Personnel')


def uses_manager_daily_target(user: User | None) -> bool:
    name = staff_role_name(user)
    return name == 'Manager' or 'manager' in name.lower()


def user_has_personal_target(user: User | None) -> bool:
    return not is_skipped_appraisal_role(staff_role_name(user))


def template_for_user(user: User | None, template: dict[str, Any] | None = None) -> dict[str, Any]:
    base = template or load_template()
    return template_for_role(base, staff_role_name(user))


def _net_sales_by_day(user_id: int, start: datetime, end: datetime) -> dict:
    sales_qs = (
        posted_sales()
        .filter(_staff_q(user_id), occurred_at__gte=start, occurred_at__lt=end)
        .annotate(day=TruncDate('occurred_at'))
        .values('day')
        .annotate(total=Sum('total'))
    )
    refund_qs = (
        SaleRefund.objects.filter(
            sale__status='completed',
            sale__occurred_at__gte=start,
            sale__occurred_at__lt=end,
        )
        .filter(
            Q(sale__served_by_id=user_id)
            | Q(sale__served_by__isnull=True, sale__cashier_id=user_id)
        )
        .annotate(day=TruncDate('sale__occurred_at'))
        .values('day')
        .annotate(total=Sum('amount'))
    )
    by_day: dict = defaultdict(lambda: Decimal('0'))
    for row in sales_qs:
        day = row['day']
        if day is None:
            continue
        by_day[day] += row['total'] or Decimal('0')
    for row in refund_qs:
        day = row['day']
        if day is None:
            continue
        by_day[day] -= row['total'] or Decimal('0')
    return {day: max(Decimal('0'), amount) for day, amount in by_day.items()}


def _month_days(year: int, month: int, today, *, include_future: bool) -> Iterable:
    last = monthrange(year, month)[1]
    for day in range(1, last + 1):
        current = datetime(year, month, day).date()
        if not include_future and current > today:
            break
        yield current


def _build_month(
    *,
    year: int,
    month: int,
    today,
    daily_net: dict,
    template: dict[str, Any],
    complete_month: bool,
) -> dict[str, Any]:
    working_days = int(template.get('working_days') or 26)
    include_future = complete_month
    days = list(_month_days(year, month, today, include_future=include_future))[:working_days]
    star_total = Decimal('0')
    month_sales = Decimal('0')
    daily_rows = []
    for day in days:
        sales = daily_net.get(day, Decimal('0'))
        rating = daily_star(sales, template)
        star_total += Decimal(str(rating['stars']))
        month_sales += sales
        daily_rows.append({'date': day.isoformat(), **rating})

    days_elapsed = len(days)
    days_remaining = max(0, working_days - days_elapsed)
    official_avg = monthly_average(star_total, working_days)
    pace_avg = monthly_average(star_total, max(days_elapsed, 1))
    four_star = is_four_star_month(official_avg, template)
    needed_points = Decimal(str(template.get('four_star_month_min_avg') or 4)) * Decimal(working_days)
    stars_needed = max(Decimal('0'), needed_points - star_total)
    progress = float(min(Decimal('1'), star_total / needed_points)) if needed_points > 0 else 1.0
    bonus = monthly_bonus(month_sales, template)
    return {
        'year': year,
        'month': month,
        'sales': float(month_sales),
        'star_total': float(star_total),
        'official_average': round(official_avg, 4),
        'pace_average': round(pace_avg, 4),
        'four_star_month': four_star,
        'progress_to_four_star': progress,
        'days_elapsed': days_elapsed,
        'working_days': working_days,
        'days_remaining': days_remaining,
        'stars_needed': float(stars_needed),
        'days': daily_rows,
        'stars': bonus['stars'],
        'bonus': bonus['bonus'],
        'bonus_label': bonus['label'],
        'next_bonus': bonus['next_bonus'],
        'next_bonus_min': bonus['next_min'],
        'amount_to_next_bonus': bonus['amount_to_next'],
        'bonus_progress': bonus['progress'],
        'tone': star_tone(official_avg if official_avg else bonus['stars']),
    }


def _build_year(
    *,
    year: int,
    today,
    daily_net: dict,
    template: dict[str, Any],
) -> dict[str, Any]:
    months = []
    averages = []
    for month in range(1, 13):
        complete = (year, month) < (today.year, today.month)
        current = (year, month) == (today.year, today.month)
        future = (year, month) > (today.year, today.month)
        if future:
            empty_bonus = monthly_bonus(0, template)
            snapshot = {
                'year': year,
                'month': month,
                'sales': 0.0,
                'star_total': 0.0,
                'official_average': 0.0,
                'pace_average': 0.0,
                'four_star_month': False,
                'progress_to_four_star': 0.0,
                'days_elapsed': 0,
                'working_days': int(template.get('working_days') or 26),
                'days_remaining': int(template.get('working_days') or 26),
                'stars_needed': float(
                    Decimal(str(template.get('four_star_month_min_avg') or 4))
                    * Decimal(int(template.get('working_days') or 26))
                ),
                'days': [],
                'stars': empty_bonus['stars'],
                'bonus': empty_bonus['bonus'],
                'bonus_label': empty_bonus['label'],
                'next_bonus': empty_bonus['next_bonus'],
                'next_bonus_min': empty_bonus['next_min'],
                'amount_to_next_bonus': empty_bonus['amount_to_next'],
                'bonus_progress': empty_bonus['progress'],
                'tone': empty_bonus['tone'],
            }
        else:
            snapshot = _build_month(
                year=year,
                month=month,
                today=today,
                daily_net=daily_net,
                template=template,
                complete_month=complete,
            )
            snapshot.pop('days', None)
        months.append(snapshot)
        averages.append(float(snapshot.get('official_average') or 0))

    result = year_end_result(averages, template)
    elapsed = today.month if today.year == year else (12 if today.year > year else 0)
    elapsed = max(0, min(12, elapsed))
    ytd = sum(averages[:elapsed]) / elapsed if elapsed else 0.0
    remaining = max(0, 12 - elapsed)
    current_avg = averages[elapsed - 1] if elapsed else 0.0
    projected_avgs = averages[:elapsed] + [current_avg] * remaining
    projected = year_end_result(projected_avgs, template)
    months_needed = int(template.get('four_star_months_required') or 8)
    progress = min(1.0, result['four_star_months'] / months_needed) if months_needed else 1.0
    return {
        'year': year,
        'months': months,
        'ytd_average': round(ytd, 4),
        'projected_annual_average': projected['annual_average'],
        'projected_qualifies': projected['qualifies'],
        'progress_to_increment': progress,
        'tone': star_tone(ytd or result['annual_average']),
        **result,
    }


def staff_snapshot(user: User, *, year: int | None = None, today=None, template=None) -> dict[str, Any]:
    today = today or timezone.localdate()
    year = int(year or today.year)
    base = template or load_template()
    if not user_has_personal_target(user):
        return {
            'staff': {
                'id': user.id,
                'username': user.username,
                'name': _display_name(user),
            },
            'policy': public_policy(base),
            'has_personal_target': False,
            'today': None,
            'month': None,
            'year': None,
            'greeting': None,
            'today_tips': None,
            'show_on_home': False,
        }
    applied = template_for_user(user, base)
    start, end = _year_bounds(year)
    daily_net = _net_sales_by_day(user.id, start, end)
    if year < today.year:
        month_today = datetime(year, 12, 31).date()
    elif year > today.year:
        month_today = datetime(year, 1, 1).date()
    else:
        month_today = today
    today_sales = daily_net.get(today, Decimal('0')) if today.year == year else Decimal('0')
    today_rating = daily_star(today_sales, applied)
    month = _build_month(
        year=year,
        month=month_today.month,
        today=month_today,
        daily_net=daily_net,
        template=applied,
        complete_month=year < today.year,
    )
    year_snap = _build_year(year=year, today=today, daily_net=daily_net, template=applied)
    greeting = greeting_copy(
        today_rating,
        month,
        year_snap,
        show_increment=bool(base.get('show_year_end_increment')),
    )
    return {
        'staff': {
            'id': user.id,
            'username': user.username,
            'name': _display_name(user),
        },
        'policy': public_policy(base),
        'today': {'date': today.isoformat(), **today_rating},
        'month': month,
        'year': year_snap,
        'greeting': greeting,
        'today_tips': pick_daily_tips(base, today),
        'show_on_home': show_on_home(),
        'has_personal_target': True,
    }


def team_snapshots(*, year: int | None = None, today=None, template=None) -> dict[str, Any]:
    today = today or timezone.localdate()
    year = int(year or today.year)
    template = template or load_template()
    start, end = _year_bounds(year)
    staff_ids = list(
        posted_sales()
        .filter(occurred_at__gte=start, occurred_at__lt=end)
        .annotate(staff_id=Coalesce('served_by_id', 'cashier_id'))
        .values_list('staff_id', flat=True)
        .distinct()
    )
    staff_ids = [sid for sid in staff_ids if sid]
    users = {
        u.id: u
        for u in User.objects.filter(id__in=staff_ids, is_active=True).select_related(
            'profile', 'profile__custom_role'
        )
    }
    results = []
    for user in sorted(users.values(), key=lambda u: _display_name(u).lower()):
        if not user_has_personal_target(user):
            continue
        snap = staff_snapshot(user, year=year, today=today, template=template)
        results.append({
            'staff': snap['staff'],
            'today': snap['today'],
            'month': {
                'sales': snap['month']['sales'],
                'stars': snap['month']['stars'],
                'bonus': snap['month']['bonus'],
                'official_average': snap['month']['official_average'],
                'four_star_month': snap['month']['four_star_month'],
                'progress_to_four_star': snap['month']['progress_to_four_star'],
                'tone': snap['month']['tone'],
            },
            'year': {
                'annual_average': snap['year']['annual_average'],
                'ytd_average': snap['year']['ytd_average'],
                'four_star_months': snap['year']['four_star_months'],
                'four_star_months_required': snap['year']['four_star_months_required'],
                'qualifies': snap['year']['qualifies'],
                'projected_qualifies': snap['year']['projected_qualifies'],
                'new_basic': snap['year']['new_basic'],
                'progress_to_increment': snap['year']['progress_to_increment'],
                'tone': snap['year']['tone'],
            },
        })
    return {
        'year': year,
        'policy': public_policy(template),
        'results': results,
    }
