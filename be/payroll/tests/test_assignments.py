from datetime import date
from decimal import Decimal

from employees.models import Employee
from payroll.models import EmployeePayAssignment, PayComponent, PayrollRun
from payroll.services import calculate_run, create_run
from payroll.starters import seed_starter_components
from utils.tests.api_test_base import SuperAdminAPITestCase


class EmployeePayAssignmentTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        seed_starter_components()
        self.emp = Employee.objects.create(
            employee_id='ASG-1',
            first_name='Ann',
            last_name='Staff',
            position='Clerk',
            department='admin',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('30000.00'),
            created_by=self.admin,
        )
        self.transport = PayComponent.objects.get(code='ALLOWANCE_TRANSPORT')
        self.ded_other = PayComponent.objects.get(code='DED_OTHER')
        self.basic = PayComponent.objects.get(code='BASIC')

    def test_individual_add_and_subtract_on_calculate(self):
        EmployeePayAssignment.objects.create(
            employee=self.emp,
            component=self.transport,
            amount=Decimal('3000.00'),
            notes='Transport for Ann',
        )
        EmployeePayAssignment.objects.create(
            employee=self.emp,
            component=self.ded_other,
            amount=Decimal('500.00'),
            notes='Uniform',
        )
        run = create_run(year=2026, month=5, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = run.payslips.get(employee=self.emp)
        self.assertEqual(slip.basic_salary, Decimal('30000.00'))
        self.assertEqual(slip.gross_pay, Decimal('33000.00'))
        self.assertEqual(slip.total_deductions, Decimal('500.00'))
        self.assertEqual(slip.net_pay, Decimal('32500.00'))

    def test_basic_override_per_employee(self):
        EmployeePayAssignment.objects.create(
            employee=self.emp,
            component=self.basic,
            amount=Decimal('35000.00'),
            notes='Market adjustment',
        )
        run = create_run(year=2026, month=6, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = run.payslips.get(employee=self.emp)
        self.assertEqual(slip.basic_salary, Decimal('35000.00'))
        self.assertEqual(slip.gross_pay, Decimal('35000.00'))
