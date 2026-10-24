"""Payroll run workflow: create → calculate → submit → approve/lock."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from employees.models import Employee
from payroll.adapters import (
    fetch_absence_deduction,
    fetch_appraisal_bonus,
    fetch_loan_deduction,
)
from payroll.engine import build_payslip_lines, money
from payroll.models import (
    EmployeePayAssignment,
    PayComponent,
    PayrollRun,
    PayrollSettings,
    Payslip,
    PayslipLine,
    RolePayPackage,
)
from payroll.starters import seed_starter_components
from utils.audit import log_audit

ZERO = Decimal('0.00')


class PayrollError(Exception):
    """Domain error with a user-facing message."""

    def __init__(self, message: str, *, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def period_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def create_run(
    *,
    year: int,
    month: int,
    user=None,
    tenant=None,
    notes: str = '',
    request=None,
) -> PayrollRun:
    if not (1 <= int(month) <= 12):
        raise PayrollError('Month must be 1–12')
    if int(year) < 2000 or int(year) > 2100:
        raise PayrollError('Year out of range')
    seed_starter_components()
    start, end = period_bounds(year, month)
    active = PayrollRun.objects.filter(tenant=tenant, year=year, month=month).exclude(
        status=PayrollRun.STATUS_CANCELLED
    )
    if active.exists():
        raise PayrollError(
            f'An active payroll run already exists for {year}-{month:02d}',
            status=409,
        )
    # Drop cancelled rows for the same period so unique_together stays clean.
    PayrollRun.objects.filter(
        tenant=tenant, year=year, month=month, status=PayrollRun.STATUS_CANCELLED
    ).delete()
    run = PayrollRun.objects.create(
        tenant=tenant,
        year=year,
        month=month,
        period_start=start,
        period_end=end,
        notes=notes or '',
        status=PayrollRun.STATUS_DRAFT,
        created_by=user,
    )
    log_audit(
        request,
        'payroll_run_created',
        run,
        module='payroll',
        object_repr=str(run),
    )
    return run


def _active_assignments(employee, on_date: date):
    qs = EmployeePayAssignment.objects.filter(
        employee=employee, is_active=True
    ).select_related('component')
    rows = []
    for a in qs:
        if a.effective_from and a.effective_from > on_date:
            continue
        if a.effective_to and a.effective_to < on_date:
            continue
        if not a.component.is_active:
            continue
        rows.append(a)
    return rows


def _component_map() -> dict[str, PayComponent]:
    return {c.code: c for c in PayComponent.objects.filter(is_active=True)}


def calculate_run(run: PayrollRun, *, user=None, request=None) -> PayrollRun:
    if run.status == PayrollRun.STATUS_LOCKED:
        raise PayrollError('Locked runs cannot be recalculated', status=409)
    if run.status == PayrollRun.STATUS_CANCELLED:
        raise PayrollError('Cancelled runs cannot be calculated', status=409)
    if run.status == PayrollRun.STATUS_PENDING_APPROVAL:
        raise PayrollError('Withdraw approval before recalculating', status=409)

    seed_starter_components()
    settings = PayrollSettings.load(run.tenant)
    components = _component_map()
    employees = Employee.objects.filter(status='active').order_by('employee_id')

    with transaction.atomic():
        run.payslips.all().delete()
        gross_total = ZERO
        ded_total = ZERO
        net_total = ZERO
        count = 0

        for emp in employees:
            result = _calculate_employee(
                emp,
                run=run,
                settings=settings,
                components=components,
            )
            if result is None:
                continue
            payslip = Payslip.objects.create(
                run=run,
                employee=emp,
                employee_id_snapshot=emp.employee_id,
                employee_name_snapshot=emp.full_name,
                position_snapshot=emp.position or '',
                department_snapshot=emp.department or '',
                bank_name_snapshot=getattr(emp, 'bank_name', '') or '',
                bank_account_snapshot=getattr(emp, 'bank_account', '') or '',
                basic_salary=result['basic'],
                gross_pay=result['gross'],
                total_deductions=result['total_deductions'],
                net_pay=result['net'],
                currency=settings.currency,
                bonus_snapshot=result['bonus_snapshot'],
                calculation_meta=result['meta'],
            )
            for line in result['lines']:
                PayslipLine.objects.create(
                    payslip=payslip,
                    component=line.get('component'),
                    code=line['code'],
                    name=line['name'],
                    kind=line['kind'],
                    amount=line['amount'],
                    is_taxable=line['is_taxable'],
                    sort_order=line['sort_order'],
                    meta=line.get('meta') or {},
                )
            gross_total += result['gross']
            ded_total += result['total_deductions']
            net_total += result['net']
            count += 1

        run.status = PayrollRun.STATUS_CALCULATED
        run.gross_total = money(gross_total)
        run.deduction_total = money(ded_total)
        run.net_total = money(net_total)
        run.employee_count = count
        run.calculated_at = timezone.now()
        run.calculated_by = user
        run.save(
            update_fields=[
                'status',
                'gross_total',
                'deduction_total',
                'net_total',
                'employee_count',
                'calculated_at',
                'calculated_by',
                'updated_at',
            ]
        )

    log_audit(
        request,
        'payroll_run_calculated',
        run,
        module='payroll',
        object_repr=str(run),
        changes={
            'employee_count': count,
            'net_total': str(run.net_total),
        },
    )
    return run


def _role_from_position(emp):
    """Fallback: match Employee.position text to an active Role name (case-insensitive)."""
    position = (getattr(emp, 'position', None) or '').strip()
    if not position:
        return None
    try:
        from accounts.models import Role

        return Role.objects.filter(name__iexact=position, is_active=True).first()
    except Exception:
        return None


def _role_for_employee(emp):
    """
    Job role for pay packages:
    1) linked login user's custom_role
    2) fallback — Employee.position matching a Role name (e.g. "Sales Personnel")
    """
    user = getattr(emp, 'user', None)
    if user is None and getattr(emp, 'user_id', None):
        try:
            from django.contrib.auth.models import User

            user = User.objects.select_related('profile', 'profile__custom_role').get(
                pk=emp.user_id
            )
        except Exception:
            user = None
    if user is not None:
        try:
            profile = user.profile
            role = getattr(profile, 'custom_role', None)
            if role is not None:
                return role
        except Exception:
            pass
    return _role_from_position(emp)


def _package_for_employee(emp) -> RolePayPackage | None:
    role = _role_for_employee(emp)
    if role is None:
        return None
    return (
        RolePayPackage.objects.filter(role=role, is_active=True)
        .prefetch_related('lines__component')
        .first()
    )


def estimate_current_pay(emp, *, on_date: date | None = None) -> dict:
    """
    Current pay preview for an employee: role package + personal Staff-pay edits.

    Does not run appraisal/loan/statutory adapters — those apply only on a payroll run.
    """
    on_date = on_date or date.today()
    settings = PayrollSettings.load(getattr(emp, 'tenant', None))
    components = _component_map()
    package = _package_for_employee(emp)
    assignments = list(_active_assignments(emp, on_date))
    basic, basic_source = _resolve_basic(
        emp, assignments=assignments, package=package
    )
    merged_rows, package_meta = _merged_pay_lines(
        emp, period_end=on_date, settings=settings, components=components
    )
    rows: list[dict] = []
    basic_comp = components.get('BASIC')
    if basic_comp:
        rows.append(
            {
                'component': basic_comp,
                'amount': basic,
                'include_zero': True,
                'meta': {'source': basic_source},
            }
        )
    rows.extend(merged_rows)
    built = build_payslip_lines(basic=basic, component_rows=rows)
    role = _role_for_employee(emp)
    return {
        'effective_basic': str(built['basic']),
        'basic_source': basic_source,
        'estimated_gross': str(built['gross']),
        'estimated_deductions': str(built['total_deductions']),
        'estimated_net': str(built['net']),
        'role_id': role.id if role else None,
        'role_name': role.name if role else None,
        'package_id': package.id if package else None,
        'package_name': package.display_name() if package else None,
        'override_count': len(
            [a for a in assignments if a.component.code != 'BASIC' or a.amount is not None]
        ),
        'inherits_package': package is not None,
        'package_line_count': package_meta.get('package_line_count') or 0,
    }


def _merged_pay_lines(emp, *, period_end, settings, components) -> tuple[list, dict]:
    """
    Merge role package defaults with per-employee assignments.

    Precedence per component: employee assignment > role package line.
    BASIC is handled separately via ``_resolve_basic``.
    """
    formula_codes = {'BONUS_APPRAISAL', 'DED_LOAN', 'DED_ABSENCE'}
    package = _package_for_employee(emp)
    assignments = list(_active_assignments(emp, period_end))
    by_code: dict[str, dict] = {}

    if package:
        for line in package.lines.all():
            if not line.is_active:
                continue
            comp = line.component
            if not comp.is_active or comp.code not in components:
                continue
            if comp.code == 'BASIC':
                continue
            if comp.is_statutory and not settings.statutory_enabled:
                continue
            if comp.code in formula_codes:
                continue
            by_code[comp.code] = {
                'component': components[comp.code],
                'amount': line.amount,
                'rate': line.rate,
                'include_zero': line.amount is not None,
                'force': line.amount is not None and money(line.amount) > ZERO,
                'meta': {
                    'source': 'role_package',
                    'package_id': package.id,
                    'role': package.role.name,
                    'notes': line.notes or '',
                },
            }

    for assignment in assignments:
        comp = assignment.component
        if comp.code == 'BASIC':
            continue
        if not comp.is_active or comp.code not in components:
            continue
        if comp.is_statutory and not settings.statutory_enabled:
            continue
        if comp.code in formula_codes:
            continue
        by_code[comp.code] = {
            'component': components[comp.code],
            'amount': assignment.amount,
            'rate': assignment.rate,
            'include_zero': assignment.amount is not None,
            'force': assignment.amount is not None and money(assignment.amount) > ZERO,
            'meta': {
                'source': 'assignment',
                'assignment_id': assignment.id,
                'notes': assignment.notes or '',
            },
        }

    meta = {
        'role': package.role.name if package else None,
        'package_id': package.id if package else None,
        'package_name': package.display_name() if package else None,
        'assignment_count': len(assignments),
        'package_line_count': len(by_code),
    }
    return list(by_code.values()), meta


def _resolve_basic(emp, *, assignments, package) -> tuple:
    """
    Basic precedence:
    1) employee BASIC assignment
    2) employee.salary
    3) role package BASIC line
    4) role package.default_basic
    5) 0
    """
    for assignment in assignments:
        if assignment.component.code == 'BASIC' and assignment.amount is not None:
            return money(assignment.amount), 'assignment'
    if emp.salary is not None:
        return money(emp.salary), 'employee.salary'
    if package:
        for line in package.lines.all():
            if (
                line.is_active
                and line.component.code == 'BASIC'
                and line.amount is not None
            ):
                return money(line.amount), 'role_package'
        if package.default_basic is not None:
            return money(package.default_basic), 'role_package.default_basic'
    return ZERO, 'none'


def _calculate_employee(emp, *, run, settings, components) -> dict | None:
    """
    Role pay package (defaults) + per-employee Staff pay (overrides).

    - Package comes from the linked user's job role.
    - Employee assignments win for the same component.
    - ``Employee.salary`` / BASIC assignment / package default set basic.
    """
    package = _package_for_employee(emp)
    assignments = list(_active_assignments(emp, run.period_end))
    basic, basic_source = _resolve_basic(
        emp, assignments=assignments, package=package
    )
    merged_rows, package_meta = _merged_pay_lines(
        emp, period_end=run.period_end, settings=settings, components=components
    )

    rows: list[dict] = []
    meta: dict = {'adapters': {}, **package_meta}

    basic_comp = components.get('BASIC')
    if basic_comp:
        rows.append(
            {
                'component': basic_comp,
                'amount': basic,
                'include_zero': True,
                'meta': {'source': basic_source},
            }
        )

    rows.extend(merged_rows)

    # Bonus adapter
    bonus_amount = ZERO
    if settings.include_appraisal_bonus and 'BONUS_APPRAISAL' in components:
        bonus = fetch_appraisal_bonus(emp, year=run.year, month=run.month)
        meta['adapters']['bonus'] = bonus.get('meta') or {}
        bonus_amount = money(bonus.get('amount'))
        if bonus_amount > ZERO or bonus.get('qualified'):
            rows.append(
                {
                    'component': components['BONUS_APPRAISAL'],
                    'amount': bonus_amount,
                    'include_zero': bonus_amount > ZERO,
                    'force': bonus_amount > ZERO,
                    'meta': bonus.get('meta') or {},
                }
            )

    # Loans stub
    if 'DED_LOAN' in components:
        loan = fetch_loan_deduction(emp, year=run.year, month=run.month)
        meta['adapters']['loans'] = loan.get('meta') or {}
        loan_amt = money(loan.get('amount'))
        if loan_amt > ZERO:
            rows.append(
                {
                    'component': components['DED_LOAN'],
                    'amount': loan_amt,
                    'force': True,
                    'meta': loan.get('meta') or {},
                }
            )

    # Attendance stub
    if 'DED_ABSENCE' in components:
        absence = fetch_absence_deduction(
            emp, year=run.year, month=run.month, basic_salary=basic
        )
        meta['adapters']['attendance'] = absence.get('meta') or {}
        abs_amt = money(absence.get('amount'))
        if abs_amt > ZERO:
            rows.append(
                {
                    'component': components['DED_ABSENCE'],
                    'amount': abs_amt,
                    'force': True,
                    'meta': absence.get('meta') or {},
                }
            )

    # Statutory — only when enabled
    if settings.statutory_enabled:
        for code in ('STAT_PAYE', 'STAT_NSSF', 'STAT_SHIF'):
            comp = components.get(code)
            if not comp:
                continue
            # Placeholder: zero until bands configured
            rows.append(
                {
                    'component': comp,
                    'amount': ZERO,
                    'include_zero': False,
                    'meta': {'source': 'statutory', 'note': 'enabled_but_no_bands'},
                }
            )

    built = build_payslip_lines(basic=basic, component_rows=rows)
    built['bonus_snapshot'] = bonus_amount
    built['meta'] = meta
    return built


def submit_run(run: PayrollRun, *, user=None, request=None) -> PayrollRun:
    if run.status != PayrollRun.STATUS_CALCULATED:
        raise PayrollError('Only calculated runs can be submitted for approval')
    if run.employee_count < 1:
        raise PayrollError('Cannot submit an empty payroll run')
    run.status = PayrollRun.STATUS_PENDING_APPROVAL
    run.submitted_at = timezone.now()
    run.submitted_by = user
    run.save(
        update_fields=['status', 'submitted_at', 'submitted_by', 'updated_at']
    )
    log_audit(
        request,
        'payroll_run_submitted',
        run,
        module='payroll',
        object_repr=str(run),
    )
    return run


def approve_and_lock(run: PayrollRun, *, user=None, request=None) -> PayrollRun:
    if run.status != PayrollRun.STATUS_PENDING_APPROVAL:
        raise PayrollError('Only runs pending approval can be locked')
    run.status = PayrollRun.STATUS_LOCKED
    run.locked_at = timezone.now()
    run.locked_by = user
    run.save(update_fields=['status', 'locked_at', 'locked_by', 'updated_at'])
    log_audit(
        request,
        'payroll_run_locked',
        run,
        module='payroll',
        object_repr=str(run),
    )
    return run


def reject_to_calculated(run: PayrollRun, *, user=None, request=None, reason: str = '') -> PayrollRun:
    if run.status != PayrollRun.STATUS_PENDING_APPROVAL:
        raise PayrollError('Only pending runs can be sent back')
    run.status = PayrollRun.STATUS_CALCULATED
    run.submitted_at = None
    run.submitted_by = None
    if reason:
        run.notes = (run.notes + '\n' if run.notes else '') + f'Rejected: {reason}'
    run.save(
        update_fields=[
            'status',
            'submitted_at',
            'submitted_by',
            'notes',
            'updated_at',
        ]
    )
    log_audit(
        request,
        'payroll_run_rejected',
        run,
        module='payroll',
        object_repr=str(run),
        changes={'reason': reason},
    )
    return run


def cancel_run(run: PayrollRun, *, user=None, request=None) -> PayrollRun:
    if run.status == PayrollRun.STATUS_LOCKED:
        raise PayrollError('Locked runs cannot be cancelled', status=409)
    run.status = PayrollRun.STATUS_CANCELLED
    run.save(update_fields=['status', 'updated_at'])
    log_audit(
        request,
        'payroll_run_cancelled',
        run,
        module='payroll',
        object_repr=str(run),
    )
    return run


def employee_for_user(user):
    """Resolve Employee for self-service: linked user first, then email."""
    if not user or not user.is_authenticated:
        return None
    linked = Employee.objects.filter(user=user).first()
    if linked:
        return linked
    email = (user.email or '').strip()
    if not email:
        return None
    return Employee.objects.filter(email__iexact=email).first()
