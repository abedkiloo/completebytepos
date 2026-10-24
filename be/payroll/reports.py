"""Payroll summary reports (JSON payloads for API / UI)."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum

from payroll.models import PayrollRun, Payslip, PayslipLine


def run_summary(run: PayrollRun) -> dict:
    slips = run.payslips.all()
    by_dept = (
        slips.values('department_snapshot')
        .annotate(
            count=Count('id'),
            gross=Sum('gross_pay'),
            deductions=Sum('total_deductions'),
            net=Sum('net_pay'),
        )
        .order_by('department_snapshot')
    )
    component_totals = (
        PayslipLine.objects.filter(payslip__run=run)
        .values('code', 'name', 'kind')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('kind', 'code')
    )
    return {
        'run_id': run.id,
        'period': run.period_label,
        'status': run.status,
        'employee_count': run.employee_count,
        'gross_total': str(run.gross_total),
        'deduction_total': str(run.deduction_total),
        'net_total': str(run.net_total),
        'by_department': [
            {
                'department': row['department_snapshot'] or '—',
                'count': row['count'],
                'gross': str(row['gross'] or 0),
                'deductions': str(row['deductions'] or 0),
                'net': str(row['net'] or 0),
            }
            for row in by_dept
        ],
        'by_component': [
            {
                'code': row['code'],
                'name': row['name'],
                'kind': row['kind'],
                'total': str(row['total'] or 0),
                'count': row['count'],
            }
            for row in component_totals
        ],
    }


def year_overview(*, year: int, tenant=None) -> dict:
    qs = PayrollRun.objects.filter(year=year).exclude(
        status=PayrollRun.STATUS_CANCELLED
    )
    if tenant is not None:
        qs = qs.filter(tenant=tenant)
    months = []
    for run in qs.order_by('month'):
        months.append(
            {
                'run_id': run.id,
                'month': run.month,
                'period': run.period_label,
                'status': run.status,
                'employee_count': run.employee_count,
                'gross_total': str(run.gross_total),
                'net_total': str(run.net_total),
            }
        )
    locked = [m for m in months if m['status'] == PayrollRun.STATUS_LOCKED]
    net_sum = sum(Decimal(m['net_total']) for m in locked) if locked else Decimal('0')
    return {
        'year': year,
        'months': months,
        'locked_net_total': str(net_sum),
        'run_count': len(months),
    }
