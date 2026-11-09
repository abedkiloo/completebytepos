"""
Sales commission adapter for payroll.

v1: net field sales attributed to the employee’s login user × commission rate %.
Rate precedence: Staff pay assignment → role package line → component default.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional

from django.db.models import Q, Sum
from django.utils import timezone

from payroll.adapters.bonus import money, resolve_user_for_employee

COMMISSION_CODE = 'EARN_COMMISSION'
DEFAULT_RATE = Decimal('0.0300')  # 3%


def _period_bounds(year: int, month: int):
    """
    Inclusive local-day bounds for a calendar month.

    Args:
        year: Four-digit year (e.g. 2026).
        month: Month 1–12.

    Returns:
        Tuple ``(start_aware, end_aware)`` for ORM datetime filters.
    """
    last = calendar.monthrange(year, month)[1]
    start_d = date(year, month, 1)
    end_d = date(year, month, last)
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(start_d, time.min), tz)
    end = timezone.make_aware(datetime.combine(end_d, time.max), tz)
    return start, end


def _staff_sale_q(user_id: int) -> Q:
    """Sales credited to this user (served_by, else cashier)."""
    return Q(served_by_id=user_id) | Q(served_by__isnull=True, cashier_id=user_id)


def net_field_sales_for_user(user_id: int, *, year: int, month: int) -> Decimal:
    """
    Net field sales for a user in a calendar month.

    Gross = completed field sales attributed to the user.
    Refunds on those sales (by refund created_at in the same month) are subtracted.
    Floor at zero.

    Args:
        user_id: Django auth user id (positive).
        year: Payroll year.
        month: Payroll month 1–12.

    Returns:
        Non-negative Decimal quantized to 0.01.
    """
    from reports.sale_scope import posted_sales
    from sales.models import SaleRefund

    start, end = _period_bounds(year, month)
    sales_qs = (
        posted_sales()
        .filter(_staff_sale_q(user_id), entry_source='field')
        .filter(occurred_at__gte=start, occurred_at__lte=end)
    )
    gross = sales_qs.aggregate(total=Sum('total'))['total'] or Decimal('0')
    gross = money(gross)

    refund_total = (
        SaleRefund.objects.filter(
            sale__in=sales_qs.values('pk'),
            created_at__gte=start,
            created_at__lte=end,
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )
    refund_total = money(refund_total)
    net = gross - refund_total
    if net < 0:
        net = Decimal('0.00')
    return money(net)


def _as_rate(value) -> Decimal:
    """Parse a percent fraction without forcing money (0.01) rounding."""
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.0001'))
    except Exception:
        return Decimal('0.0000')


def resolve_commission_rate(employee) -> tuple[Decimal, str]:
    """
    Resolve commission rate (fraction, e.g. 0.03 = 3%).

    Args:
        employee: ``employees.Employee`` instance.

    Returns:
        Tuple ``(rate, source)`` where source is assignment|role_package|
        component_default|none.
    """
    from payroll.models import EmployeePayAssignment, PayComponent
    from payroll.services import _package_for_employee

    today = timezone.localdate()
    assignment = (
        EmployeePayAssignment.objects.filter(
            employee=employee,
            component__code=COMMISSION_CODE,
            is_active=True,
        )
        .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=today))
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .select_related('component')
        .first()
    )
    if assignment is not None and assignment.rate is not None:
        return _as_rate(assignment.rate), 'assignment'

    package = _package_for_employee(employee)
    if package is not None:
        for line in package.lines.all():
            if (
                line.is_active
                and line.component.code == COMMISSION_CODE
                and line.rate is not None
            ):
                return _as_rate(line.rate), 'role_package'

    comp = PayComponent.objects.filter(code=COMMISSION_CODE, is_active=True).first()
    if comp is not None and comp.default_rate is not None:
        rate = _as_rate(comp.default_rate)
        if rate > 0:
            return rate, 'component_default'
    return Decimal('0.0000'), 'none'


def sales_commission_enabled() -> bool:
    """
    True when the sellable feature and store setting both allow commission.

    Returns:
        bool — False when feature off or settings flag off.
    """
    try:
        from settings.module_features import is_module_feature_enabled

        if not is_module_feature_enabled('payroll', 'sales_commission'):
            return False
    except Exception:
        pass
    try:
        from payroll.models import PayrollSettings

        return bool(PayrollSettings.load().include_sales_commission)
    except Exception:
        return False


def fetch_sales_commission(
    employee,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """
    Compute field-sales commission for one employee and payroll month.

    Args:
        employee: Employee row (may lack linked user → amount 0).
        year: Run year.
        month: Run month 1–12.

    Returns:
        Dict with ``amount`` (Decimal), ``qualified`` (bool), and ``meta`` audit.
    """
    empty_meta = {
        'source': 'sales_commission',
        'available': True,
        'field_only': True,
        'period': f'{year}-{month:02d}',
    }
    empty = {'amount': Decimal('0.00'), 'qualified': False, 'meta': empty_meta}

    if not sales_commission_enabled():
        return {
            **empty,
            'meta': {**empty_meta, 'available': False, 'reason': 'commission_disabled'},
        }

    user = resolve_user_for_employee(employee)
    if user is None:
        return {
            **empty,
            'meta': {**empty_meta, 'matched_user': False, 'reason': 'no_user'},
        }

    rate, rate_source = resolve_commission_rate(employee)
    base = net_field_sales_for_user(user.id, year=year, month=month)
    amount = money(base * rate) if rate > 0 and base > 0 else Decimal('0.00')

    return {
        'amount': amount,
        'qualified': amount > 0,
        'meta': {
            **empty_meta,
            'matched_user': True,
            'user_id': user.id,
            'sales_base': str(base),
            'rate': str(rate),
            'rate_source': rate_source,
            'rate_percent': str((rate * Decimal('100')).quantize(Decimal('0.01'))),
        },
    }


def ensure_field_sales_commission_package(
    *,
    default_rate: Optional[Decimal] = None,
    default_basic: Optional[Decimal] = None,
) -> Any:
    """
    Ensure Field Sales role has an active pay package with commission line.

    Args:
        default_rate: Fraction rate (default 0.03). Capped to 0–1 style values.
        default_basic: Optional package default basic when creating anew.

    Returns:
        ``RolePayPackage`` instance (existing or created).

    Raises:
        LookupError: When Field Sales role is missing from the database.
    """
    from accounts.models import Role
    from accounts.role_definitions import ROLE_FIELD_AGENT
    from payroll.models import PayComponent, RolePayPackage, RolePayPackageLine
    from payroll.starters import seed_starter_components

    seed_starter_components()
    role = Role.objects.filter(name=ROLE_FIELD_AGENT).first()
    if role is None:
        raise LookupError(f'Role {ROLE_FIELD_AGENT!r} not found — sync roles first.')

    rate = default_rate if default_rate is not None else DEFAULT_RATE
    package, _ = RolePayPackage.objects.get_or_create(
        role=role,
        defaults={
            'name': f'{ROLE_FIELD_AGENT} package',
            'default_basic': default_basic,
            'is_active': True,
            'notes': 'General template — edit Staff pay for one person only.',
        },
    )
    if not package.is_active:
        package.is_active = True
        package.save(update_fields=['is_active', 'updated_at'])

    component = PayComponent.objects.get(code=COMMISSION_CODE)
    line, created = RolePayPackageLine.objects.get_or_create(
        package=package,
        component=component,
        defaults={
            'rate': rate,
            'amount': None,
            'is_active': True,
            'notes': 'Net field sales × rate',
            'sort_order': 25,
        },
    )
    if not created and line.rate is None:
        line.rate = rate
        line.is_active = True
        line.save(update_fields=['rate', 'is_active'])
    return package
