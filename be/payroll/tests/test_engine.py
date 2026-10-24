from decimal import Decimal

from django.test import SimpleTestCase

from payroll.engine import build_payslip_lines, money, resolve_component_amount
from payroll.models import PayComponent


class PayrollEngineTests(SimpleTestCase):
    def test_money_quantize(self):
        self.assertEqual(money('10.456'), Decimal('10.46'))
        self.assertEqual(money(None), Decimal('0.00'))

    def test_fixed_and_percent_basic(self):
        basic_comp = PayComponent(
            code='BASIC',
            name='Basic',
            kind=PayComponent.KIND_EARNING,
            calculation_type=PayComponent.CALC_FIXED,
            default_amount=Decimal('50000'),
            sort_order=10,
        )
        housing = PayComponent(
            code='ALLOWANCE_HOUSING',
            name='Housing',
            kind=PayComponent.KIND_EARNING,
            calculation_type=PayComponent.CALC_PERCENT_BASIC,
            default_rate=Decimal('0.15'),
            sort_order=40,
        )
        advance = PayComponent(
            code='DED_ADVANCE',
            name='Advance',
            kind=PayComponent.KIND_DEDUCTION,
            calculation_type=PayComponent.CALC_FIXED,
            default_amount=Decimal('2000'),
            sort_order=110,
        )
        result = build_payslip_lines(
            basic=Decimal('50000'),
            component_rows=[
                {'component': basic_comp, 'amount': Decimal('50000'), 'include_zero': True},
                {'component': housing},
                {'component': advance, 'force': True},
            ],
        )
        self.assertEqual(result['basic'], Decimal('50000.00'))
        self.assertEqual(result['gross'], Decimal('57500.00'))
        self.assertEqual(result['total_deductions'], Decimal('2000.00'))
        self.assertEqual(result['net'], Decimal('55500.00'))

    def test_resolve_percent_gross(self):
        comp = PayComponent(
            code='X',
            name='X',
            kind=PayComponent.KIND_EARNING,
            calculation_type=PayComponent.CALC_PERCENT_GROSS,
            default_rate=Decimal('0.10'),
        )
        amt = resolve_component_amount(
            comp, basic=Decimal('100'), gross_so_far=Decimal('1000')
        )
        self.assertEqual(amt, Decimal('100.00'))
