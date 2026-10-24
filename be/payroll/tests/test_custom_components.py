from datetime import date
from decimal import Decimal

from employees.models import Employee
from payroll.models import EmployeePayAssignment, PayComponent
from payroll.services import calculate_run, create_run
from utils.tests.api_test_base import SuperAdminAPITestCase


class CustomPayComponentTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        self.emp = Employee.objects.create(
            employee_id='FOOD-1',
            first_name='Kim',
            last_name='Cook',
            position='Cook',
            department='kitchen',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('25000.00'),
            created_by=self.admin,
        )

    def test_create_food_allowance_via_api_and_payslip(self):
        res = self.client.post(
            '/api/payroll/components/',
            {
                'code': 'FOOD_ALLOWANCE',
                'name': 'Food allowance',
                'kind': 'earning',
                'calculation_type': 'fixed',
                'default_amount': '1500.00',
                'is_taxable': True,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data['code'], 'FOOD_ALLOWANCE')
        self.assertFalse(res.data['is_statutory'])
        self.assertTrue(res.data['is_active'])

        food = PayComponent.objects.get(code='FOOD_ALLOWANCE')
        EmployeePayAssignment.objects.create(
            employee=self.emp,
            component=food,
            amount=Decimal('1500.00'),
            notes='Monthly meals',
        )
        run = create_run(year=2026, month=10, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = run.payslips.get(employee=self.emp)
        self.assertEqual(slip.gross_pay, Decimal('26500.00'))
        codes = set(slip.lines.values_list('code', flat=True))
        self.assertIn('FOOD_ALLOWANCE', codes)
        self.assertEqual(slip.lines.get(code='FOOD_ALLOWANCE').name, 'Food allowance')

    def test_duplicate_code_rejected(self):
        PayComponent.objects.create(
            code='FOOD_ALLOWANCE',
            name='Food allowance',
            kind=PayComponent.KIND_EARNING,
        )
        res = self.client.post(
            '/api/payroll/components/',
            {
                'code': 'food_allowance',
                'name': 'Food again',
                'kind': 'earning',
                'calculation_type': 'fixed',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('code', res.data)
