"""Seed starter pay-component library and dormant statutory rules."""

from decimal import Decimal

from payroll.models import PayComponent, StatutoryRule

STARTER_COMPONENTS = [
    {
        'code': 'BASIC',
        'name': 'Basic salary',
        'kind': PayComponent.KIND_EARNING,
        'calculation_type': PayComponent.CALC_FIXED,
        'default_amount': Decimal('0.00'),
        'is_taxable': True,
        'is_statutory': False,
        'sort_order': 10,
        'description': 'Monthly basic from employee record',
    },
    {
        'code': 'BONUS_APPRAISAL',
        'name': 'Target delivery bonus',
        'kind': PayComponent.KIND_EARNING,
        'calculation_type': PayComponent.CALC_FORMULA,
        'default_amount': Decimal('0.00'),
        'is_taxable': True,
        'is_statutory': False,
        'sort_order': 20,
        'description': 'Monthly bonus from appraisals adapter (snapshot at calculate)',
    },
    {
        'code': 'ALLOWANCE_TRANSPORT',
        'name': 'Transport allowance',
        'kind': PayComponent.KIND_EARNING,
        'calculation_type': PayComponent.CALC_FIXED,
        'default_amount': Decimal('0.00'),
        'is_taxable': True,
        'is_statutory': False,
        'sort_order': 30,
    },
    {
        'code': 'ALLOWANCE_HOUSING',
        'name': 'Housing allowance',
        'kind': PayComponent.KIND_EARNING,
        'calculation_type': PayComponent.CALC_PERCENT_BASIC,
        'default_rate': Decimal('0.1500'),
        'is_taxable': True,
        'is_statutory': False,
        'sort_order': 40,
    },
    {
        'code': 'DED_ADVANCE',
        'name': 'Salary advance',
        'kind': PayComponent.KIND_DEDUCTION,
        'calculation_type': PayComponent.CALC_FIXED,
        'default_amount': Decimal('0.00'),
        'is_taxable': False,
        'is_statutory': False,
        'sort_order': 110,
    },
    {
        'code': 'DED_LOAN',
        'name': 'Loan repayment',
        'kind': PayComponent.KIND_DEDUCTION,
        'calculation_type': PayComponent.CALC_FORMULA,
        'default_amount': Decimal('0.00'),
        'is_taxable': False,
        'is_statutory': False,
        'sort_order': 120,
        'description': 'Filled by loans adapter when HR loans module exists',
    },
    {
        'code': 'DED_ABSENCE',
        'name': 'Absence / unpaid leave',
        'kind': PayComponent.KIND_DEDUCTION,
        'calculation_type': PayComponent.CALC_FORMULA,
        'default_amount': Decimal('0.00'),
        'is_taxable': False,
        'is_statutory': False,
        'sort_order': 130,
        'description': 'Filled by attendance adapter when attendance module exists',
    },
    {
        'code': 'STAT_PAYE',
        'name': 'PAYE',
        'kind': PayComponent.KIND_DEDUCTION,
        'calculation_type': PayComponent.CALC_FORMULA,
        'default_amount': Decimal('0.00'),
        'is_taxable': False,
        'is_statutory': True,
        'sort_order': 200,
        'description': 'Dormant until statutory_enabled',
    },
    {
        'code': 'STAT_NSSF',
        'name': 'NSSF',
        'kind': PayComponent.KIND_DEDUCTION,
        'calculation_type': PayComponent.CALC_FORMULA,
        'default_amount': Decimal('0.00'),
        'is_taxable': False,
        'is_statutory': True,
        'sort_order': 210,
    },
    {
        'code': 'STAT_SHIF',
        'name': 'SHIF / NHIF',
        'kind': PayComponent.KIND_DEDUCTION,
        'calculation_type': PayComponent.CALC_FORMULA,
        'default_amount': Decimal('0.00'),
        'is_taxable': False,
        'is_statutory': True,
        'sort_order': 220,
    },
]

STATUTORY_STARTERS = [
    {
        'code': 'PAYE',
        'name': 'Pay As You Earn',
        'component_code': 'STAT_PAYE',
        'is_active': False,
        'config': {'note': 'Configure bands when enabling statutory'},
    },
    {
        'code': 'NSSF',
        'name': 'National Social Security Fund',
        'component_code': 'STAT_NSSF',
        'is_active': False,
        'config': {},
    },
    {
        'code': 'SHIF',
        'name': 'Social Health Insurance Fund',
        'component_code': 'STAT_SHIF',
        'is_active': False,
        'config': {},
    },
]


def seed_starter_components(*, force_inactive_statutory: bool = True) -> int:
    """Create missing starter components. Returns count created."""
    created = 0
    for row in STARTER_COMPONENTS:
        defaults = {k: v for k, v in row.items() if k != 'code'}
        _, was_created = PayComponent.objects.get_or_create(
            code=row['code'], defaults=defaults
        )
        if was_created:
            created += 1
    for row in STATUTORY_STARTERS:
        component = PayComponent.objects.filter(code=row['component_code']).first()
        _, was_created = StatutoryRule.objects.get_or_create(
            code=row['code'],
            defaults={
                'name': row['name'],
                'component': component,
                'is_active': False if force_inactive_statutory else row['is_active'],
                'config': row.get('config') or {},
            },
        )
        if was_created:
            created += 1
    return created
