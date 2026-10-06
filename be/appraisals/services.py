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
    increment_progress_message,
    is_four_star_month,
    monthly_average,
    monthly_bonus,
    star_tone,
    year_end_result,
)
from .models import AppraisalSalaryIncrement
from .policy import (
    PolicyError,
    load_template,
    public_policy,
    show_on_home,
    staff_facing,
    template_at_date,
    template_for_role,
    is_skipped_appraisal_role,
)
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


def _join_date(user: User | None):
    if user is None:
        return None
    try:
        from employees.models import Employee

        employee = _employee_for_user(user)
        if employee and getattr(employee, 'hire_date', None):
            return employee.hire_date
    except Exception:
        pass
    raw = getattr(user, 'date_joined', None)
    if raw is None:
        return None
    if timezone.is_aware(raw):
        return timezone.localtime(raw).date()
    return raw.date() if hasattr(raw, 'date') else raw


def _employee_for_user(user: User | None):
    if user is None:
        return None
    email = (getattr(user, 'email', '') or '').strip()
    if not email:
        return None
    try:
        from employees.models import Employee

        return Employee.objects.filter(email__iexact=email).order_by('-id').first()
    except Exception:
        return None


def _apply_employee_salary(user: User | None, template: dict[str, Any]) -> dict[str, Any]:
    applied = dict(template)
    employee = _employee_for_user(user)
    if employee is not None and employee.salary is not None:
        applied['basic_pay'] = float(employee.salary)
    return applied


def _applied_for_day(
    template: dict[str, Any],
    *,
    base_template=None,
    role_name: str | None = None,
    on_date=None,
) -> dict[str, Any]:
    if base_template is None or not role_name:
        return template
    return template_for_role(template_at_date(base_template, on_date), role_name)


def _cycle_eligible(hire_date, year: int, month: int) -> bool:
    """Incomplete first cycle (joined after month start) cannot qualify as a 4-star month."""
    if hire_date is None:
        return True
    month_start = datetime(year, month, 1).date()
    return hire_date <= month_start


def _build_month(
    *,
    year: int,
    month: int,
    today,
    daily_net: dict,
    template: dict[str, Any],
    complete_month: bool,
    hire_date=None,
    base_template=None,
    role_name: str | None = None,
) -> dict[str, Any]:
    last = monthrange(year, month)[1]
    month_on = datetime(year, month, last).date()
    if month_on > today:
        month_on = today
    month_end_applied = _applied_for_day(
        template,
        base_template=base_template,
        role_name=role_name,
        on_date=month_on,
    )
    working_days = int(month_end_applied.get('working_days') or template.get('working_days') or 26)
    include_future = complete_month
    days = list(_month_days(year, month, today, include_future=include_future))[:working_days]
    star_total = Decimal('0')
    month_sales = Decimal('0')
    daily_rows = []
    version_label = str((base_template or template).get('active_from') or '')
    for day in days:
        if hire_date and day < hire_date:
            continue
        applied = _applied_for_day(
            template, base_template=base_template, role_name=role_name, on_date=day
        )
        sales = daily_net.get(day, Decimal('0'))
        rating = daily_star(sales, applied)
        star_total += Decimal(str(rating['stars']))
        month_sales += sales
        daily_rows.append({
            'date': day.isoformat(),
            'config_version': str(applied.get('active_from') or version_label),
            **rating,
        })

    days_elapsed = len(daily_rows)
    days_remaining = max(0, working_days - len(days))
    official_avg = monthly_average(star_total, working_days)
    pace_avg = monthly_average(star_total, max(days_elapsed, 1))
    eligible = _cycle_eligible(hire_date, year, month)
    four_star = eligible and is_four_star_month(official_avg, month_end_applied)
    needed_points = Decimal(
        str(month_end_applied.get('four_star_month_min_avg') or 4)
    ) * Decimal(working_days)
    stars_needed = max(Decimal('0'), needed_points - star_total)
    progress = float(min(Decimal('1'), star_total / needed_points)) if needed_points > 0 else 1.0
    bonus = monthly_bonus(month_sales, month_end_applied)
    daily_target = float(month_end_applied.get('daily_target') or 0)
    four_star_days = sum(1 for row in daily_rows if float(row.get('stars') or 0) >= 4)
    return {
        'year': year,
        'month': month,
        'sales': float(month_sales),
        'expected_sales': daily_target * working_days,
        'star_total': float(star_total),
        'official_average': round(official_avg, 4),
        'pace_average': round(pace_avg, 4),
        'four_star_month': four_star,
        'four_star_month_eligible': eligible,
        'four_star_days': four_star_days,
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
    hire_date=None,
    base_template=None,
    role_name: str | None = None,
) -> dict[str, Any]:
    months = []
    averages = []
    for month in range(1, 13):
        complete = (year, month) < (today.year, today.month)
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
                'four_star_month_eligible': _cycle_eligible(hire_date, year, month),
                'four_star_days': 0,
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
                hire_date=hire_date,
                base_template=base_template,
                role_name=role_name,
            )
            snapshot.pop('days', None)
        months.append(snapshot)
        averages.append(float(snapshot.get('official_average') or 0))

    result = year_end_result(averages, template)
    counted = sum(1 for snap in months if snap.get('four_star_month'))
    result['four_star_months'] = counted
    annual_needed = float(template.get('annual_avg_required') or 4)
    months_needed = int(template.get('four_star_months_required') or 8)
    result['qualifies'] = result['annual_average'] >= annual_needed and counted >= months_needed
    if not result['qualifies']:
        result['increment_awarded'] = 0.0
        result['new_basic'] = float(result.get('basic_pay') or 0)
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
            'staff_facing': staff_facing(),
        }
    applied = _apply_employee_salary(user, template_for_user(user, base))
    hire_date = _join_date(user)
    role_name = staff_role_name(user)
    start, end = _year_bounds(year)
    daily_net = _net_sales_by_day(user.id, start, end)
    if year < today.year:
        month_today = datetime(year, 12, 31).date()
    elif year > today.year:
        month_today = datetime(year, 1, 1).date()
    else:
        month_today = today
    today_applied = _applied_for_day(
        applied, base_template=base, role_name=role_name, on_date=today
    )
    today_applied = _apply_employee_salary(user, today_applied)
    today_sales = daily_net.get(today, Decimal('0')) if today.year == year else Decimal('0')
    today_rating = daily_star(today_sales, today_applied)
    month = _build_month(
        year=year,
        month=month_today.month,
        today=month_today,
        daily_net=daily_net,
        template=applied,
        complete_month=year < today.year,
        hire_date=hire_date,
        base_template=base,
        role_name=role_name,
    )
    year_snap = _build_year(
        year=year,
        today=today,
        daily_net=daily_net,
        template=applied,
        hire_date=hire_date,
        base_template=base,
        role_name=role_name,
    )
    greeting = greeting_copy(
        today_rating,
        month,
        year_snap,
        show_increment=bool(base.get('show_year_end_increment')),
    )
    year_snap['increment_message'] = (
        increment_progress_message(year_snap, applied)
        if base.get('show_year_end_increment')
        else ''
    )
    year_snap['increment'] = sync_salary_increment(
        user, year_snap, role_name, persist=today.year > year
    )
    return {
        'staff': {
            'id': user.id,
            'username': user.username,
            'name': _display_name(user),
            'role': role_name,
            'join_date': hire_date.isoformat() if hire_date else None,
        },
        'policy': public_policy(base),
        'sales_basis': applied.get('sales_basis') or 'posted_net',
        'today': {'date': today.isoformat(), **today_rating},
        'month': month,
        'year': year_snap,
        'greeting': greeting,
        'today_tips': pick_daily_tips(base, today),
        'show_on_home': show_on_home(),
        'staff_facing': staff_facing(),
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
                'expected_sales': snap['month'].get('expected_sales'),
                'stars': snap['month']['stars'],
                'bonus': snap['month']['bonus'],
                'official_average': snap['month']['official_average'],
                'four_star_month': snap['month']['four_star_month'],
                'four_star_days': snap['month'].get('four_star_days'),
                'next_bonus': snap['month'].get('next_bonus'),
                'amount_to_next_bonus': snap['month'].get('amount_to_next_bonus'),
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
            'annual_status': _annual_status(snap),
        })
    return {
        'year': year,
        'policy': public_policy(template),
        'results': results,
        'insights': build_team_insights(results, template),
    }


def _annual_status(snap: dict[str, Any]) -> str:
    year = snap.get('year') or {}
    if year.get('qualifies') or year.get('projected_qualifies'):
        return 'On track'
    needed = int(year.get('four_star_months_required') or 8)
    have = int(year.get('four_star_months') or 0)
    if needed - have == 1:
        return 'Close'
    return 'At risk'


def build_team_insights(results: list[dict[str, Any]], template: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in results if row.get('today')]
    today_hitting = sum(1 for row in rows if float((row.get('today') or {}).get('stars') or 0) >= 4)
    today_below = max(0, len(rows) - today_hitting)
    four_star_avg = sum(
        1
        for row in rows
        if float((row.get('month') or {}).get('official_average') or 0)
        >= float(template.get('four_star_month_min_avg') or 4)
    )
    bonuses = sum(float((row.get('month') or {}).get('bonus') or 0) for row in rows)
    close = sum(
        1
        for row in rows
        if int((row.get('year') or {}).get('four_star_months_required') or 8)
        - int((row.get('year') or {}).get('four_star_months') or 0)
        == 1
        and not (row.get('year') or {}).get('qualifies')
    )
    at_risk = sum(1 for row in rows if (row.get('annual_status') == 'At risk'))
    avg_stars = (
        sum(float((row.get('month') or {}).get('official_average') or 0) for row in rows) / len(rows)
        if rows
        else 0
    )
    projected_increments = sum(
        1 for row in rows if (row.get('year') or {}).get('projected_qualifies')
    )
    total_today = sum(float((row.get('today') or {}).get('sales') or 0) for row in rows)
    total_month = sum(float((row.get('month') or {}).get('sales') or 0) for row in rows)
    lines = []
    if rows:
        lines.append(
            f'{four_star_avg} employee{"s" if four_star_avg != 1 else ""} '
            f'{"are" if four_star_avg != 1 else "is"} currently averaging 4 Stars or above.'
        )
        if close:
            lines.append(
                f'{close} employee{"s" if close != 1 else ""} '
                f'{"are" if close != 1 else "is"} one 4-Star month away from the annual increment.'
            )
        role_avgs: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            role = (row.get('staff') or {}).get('role') or 'Sales'
            role_avgs[role].append(float((row.get('month') or {}).get('official_average') or 0))
        for role, values in sorted(role_avgs.items(), key=lambda item: item[0].lower())[:4]:
            mean = sum(values) / len(values)
            lines.append(f'{role} averaging {mean:.1f} Stars this month.')
        lines.append(f'KES {int(bonuses):,} in monthly bonuses is currently projected.')
        if projected_increments:
            lines.append(
                f'{projected_increments} employee{"s" if projected_increments != 1 else ""} '
                f'projected to qualify for the annual increment this year.'
            )
    return {
        'headcount': len(rows),
        'total_today_sales': total_today,
        'total_month_sales': total_month,
        'hitting_target_today': today_hitting,
        'below_target_today': today_below,
        'four_star_today': today_hitting,
        'four_star_month_average': four_star_avg,
        'average_stars_today': round(avg_stars, 2),
        'total_monthly_bonus': bonuses,
        'close_to_increment': close,
        'at_risk': at_risk,
        'projected_increments': projected_increments,
        'lines': lines,
    }


def serialize_increment(row: AppraisalSalaryIncrement | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        'id': row.id,
        'user_id': row.user_id,
        'year': row.year,
        'role_name': row.role_name,
        'previous_basic': float(row.previous_basic),
        'increment_amount': float(row.increment_amount),
        'new_basic': float(row.new_basic),
        'annual_average': row.annual_average,
        'four_star_months': row.four_star_months,
        'four_star_months_required': row.four_star_months_required,
        'qualifies': row.qualifies,
        'status': row.status,
        'effective_date': row.effective_date.isoformat() if row.effective_date else None,
        'reason': row.reason,
        'approved_by_id': row.approved_by_id,
        'approved_at': row.approved_at.isoformat() if row.approved_at else None,
    }


def _increment_payload(user: User, year_snap: dict[str, Any], role_name: str) -> dict[str, Any]:
    qualifies = bool(year_snap.get('qualifies'))
    return {
        'role_name': role_name,
        'previous_basic': year_snap.get('basic_pay') or 0,
        'increment_amount': year_snap.get('increment_awarded') or 0,
        'new_basic': year_snap.get('new_basic') or year_snap.get('basic_pay') or 0,
        'annual_average': year_snap.get('annual_average') or 0,
        'four_star_months': year_snap.get('four_star_months') or 0,
        'four_star_months_required': year_snap.get('four_star_months_required') or 8,
        'qualifies': qualifies,
        'status': (
            AppraisalSalaryIncrement.STATUS_PENDING
            if qualifies
            else AppraisalSalaryIncrement.STATUS_NOT_ELIGIBLE
        ),
    }


def sync_salary_increment(
    user: User,
    year_snap: dict[str, Any],
    role_name: str,
    *,
    persist: bool,
) -> dict[str, Any] | None:
    payload = _increment_payload(user, year_snap, role_name)
    if not persist:
        existing = AppraisalSalaryIncrement.objects.filter(
            user=user, year=year_snap.get('year')
        ).first()
        if existing:
            return serialize_increment(existing)
        return {**payload, 'id': None, 'effective_date': None, 'approved_by_id': None, 'approved_at': None}
    row, _created = AppraisalSalaryIncrement.objects.get_or_create(
        user=user,
        year=int(year_snap.get('year')),
        defaults=payload,
    )
    if row.status == AppraisalSalaryIncrement.STATUS_APPROVED:
        return serialize_increment(row)
    for key, value in payload.items():
        setattr(row, key, value)
    row.save()
    return serialize_increment(row)


def list_salary_increments(*, year: int | None = None) -> list[dict[str, Any]]:
    qs = AppraisalSalaryIncrement.objects.select_related('user', 'approved_by')
    if year:
        qs = qs.filter(year=year)
    return [serialize_increment(row) for row in qs]


def decide_salary_increment(
    increment_id: int,
    *,
    user,
    request=None,
    approve: bool,
    reason: str = '',
    effective_date=None,
) -> dict[str, Any]:
    try:
        row = AppraisalSalaryIncrement.objects.select_related('user').get(pk=increment_id)
    except AppraisalSalaryIncrement.DoesNotExist as exc:
        raise PolicyError('Salary increment record not found.') from exc
    if row.status == AppraisalSalaryIncrement.STATUS_APPROVED:
        raise PolicyError('This increment has already been approved.')
    if approve:
        if not row.qualifies:
            raise PolicyError('Employee does not qualify for an increment.')
        row.status = AppraisalSalaryIncrement.STATUS_APPROVED
        row.approved_by = user
        row.approved_at = timezone.now()
        row.effective_date = effective_date or timezone.localdate()
        row.reason = (reason or '')[:500]
        row.save()
        employee = _employee_for_user(row.user)
        if employee is not None:
            employee.salary = row.new_basic
            employee.save(update_fields=['salary', 'updated_at'])
    else:
        row.status = AppraisalSalaryIncrement.STATUS_REJECTED
        row.approved_by = user
        row.approved_at = timezone.now()
        row.reason = (reason or '')[:500]
        row.save()
    try:
        from accounts.models import AuditLog
        from utils.audit import log_audit

        log_audit(
            request,
            AuditLog.ACTION_UPDATE,
            row,
            module='appraisals',
            object_repr=f'Salary increment {row.user_id}:{row.year}',
            changes={
                'status': row.status,
                'previous_basic': float(row.previous_basic),
                'new_basic': float(row.new_basic),
                'reason': row.reason,
            },
        )
    except Exception:
        pass
    return serialize_increment(row)
