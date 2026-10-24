"""Payroll calculation engine — pure Decimal math, no side effects on locked runs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from payroll.models import PayComponent

ZERO = Decimal('0.00')


def money(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0)).quantize(Decimal('0.01'))
    except Exception:
        return ZERO


def resolve_component_amount(
    component: PayComponent,
    *,
    basic: Decimal,
    gross_so_far: Decimal,
    assignment_amount: Decimal | None = None,
    assignment_rate: Decimal | None = None,
) -> Decimal:
    """
    Compute one component amount from type + overrides.

    Per-employee ``assignment_amount`` always wins when set (fixed cash add/subtract
    for that person, even if the template component is percent-based).
    """
    if assignment_amount is not None:
        return money(assignment_amount)

    if component.calculation_type == PayComponent.CALC_FIXED:
        return money(component.default_amount)

    rate = (
        assignment_rate
        if assignment_rate is not None
        else Decimal(str(component.default_rate or 0))
    )
    if component.calculation_type == PayComponent.CALC_PERCENT_BASIC:
        return money(basic * rate)
    if component.calculation_type == PayComponent.CALC_PERCENT_GROSS:
        return money(gross_so_far * rate)
    return money(component.default_amount)


def build_payslip_lines(
    *,
    basic: Decimal,
    component_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Build ordered payslip lines and totals.

    ``component_rows`` items:
      {component, amount (optional override), rate (optional), meta (optional), skip?}
    """
    basic = money(basic)
    earnings: list[dict[str, Any]] = []
    deductions: list[dict[str, Any]] = []
    employer: list[dict[str, Any]] = []

    # Always ensure BASIC is first if not already present.
    codes = {r['component'].code for r in component_rows if r.get('component')}
    if 'BASIC' not in codes:
        basic_comp = PayComponent(
            code='BASIC',
            name='Basic salary',
            kind=PayComponent.KIND_EARNING,
            calculation_type=PayComponent.CALC_FIXED,
            default_amount=basic,
            sort_order=10,
            is_taxable=True,
        )
        component_rows = [
            {'component': basic_comp, 'amount': basic, 'meta': {'source': 'employee.salary'}}
        ] + list(component_rows)

    gross = ZERO
    # Pass 1: fixed + percent_basic earnings (not percent_gross yet)
    pending_gross_pct: list[dict[str, Any]] = []
    for row in component_rows:
        if row.get('skip'):
            continue
        comp: PayComponent = row['component']
        if comp.kind != PayComponent.KIND_EARNING:
            continue
        if comp.calculation_type == PayComponent.CALC_PERCENT_GROSS:
            pending_gross_pct.append(row)
            continue
        amount = resolve_component_amount(
            comp,
            basic=basic,
            gross_so_far=gross,
            assignment_amount=row.get('amount'),
            assignment_rate=row.get('rate'),
        )
        if amount == ZERO and comp.code not in ('BASIC',) and not row.get('force'):
            # Still include BASIC even at 0; skip other zero optional lines unless forced
            if not row.get('include_zero'):
                continue
        line = _line_dict(comp, amount, row.get('meta') or {})
        earnings.append(line)
        if comp.code == 'BASIC':
            # Replace basic with resolved amount
            basic = amount
        gross += amount

    for row in pending_gross_pct:
        comp = row['component']
        amount = resolve_component_amount(
            comp,
            basic=basic,
            gross_so_far=gross,
            assignment_amount=row.get('amount'),
            assignment_rate=row.get('rate'),
        )
        if amount == ZERO and not row.get('include_zero') and not row.get('force'):
            continue
        line = _line_dict(comp, amount, row.get('meta') or {})
        earnings.append(line)
        gross += amount

    total_deductions = ZERO
    for row in component_rows:
        if row.get('skip'):
            continue
        comp = row['component']
        if comp.kind != PayComponent.KIND_DEDUCTION:
            continue
        amount = resolve_component_amount(
            comp,
            basic=basic,
            gross_so_far=gross,
            assignment_amount=row.get('amount'),
            assignment_rate=row.get('rate'),
        )
        if amount == ZERO and not row.get('include_zero') and not row.get('force'):
            continue
        line = _line_dict(comp, amount, row.get('meta') or {})
        deductions.append(line)
        total_deductions += amount

    for row in component_rows:
        if row.get('skip'):
            continue
        comp = row['component']
        if comp.kind != PayComponent.KIND_EMPLOYER:
            continue
        amount = resolve_component_amount(
            comp,
            basic=basic,
            gross_so_far=gross,
            assignment_amount=row.get('amount'),
            assignment_rate=row.get('rate'),
        )
        if amount == ZERO and not row.get('include_zero'):
            continue
        employer.append(_line_dict(comp, amount, row.get('meta') or {}))

    net = money(gross - total_deductions)
    return {
        'basic': money(basic),
        'gross': money(gross),
        'total_deductions': money(total_deductions),
        'net': net,
        'earnings': earnings,
        'deductions': deductions,
        'employer': employer,
        'lines': earnings + deductions + employer,
    }


def _line_dict(comp: PayComponent, amount: Decimal, meta: dict) -> dict[str, Any]:
    return {
        'component': comp if getattr(comp, 'pk', None) else None,
        'code': comp.code,
        'name': comp.name,
        'kind': comp.kind,
        'amount': money(amount),
        'is_taxable': bool(comp.is_taxable),
        'sort_order': int(comp.sort_order or 100),
        'meta': meta,
    }
