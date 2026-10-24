from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from employees.models import Employee
from payroll.models import EmployeePayAssignment, PayComponent, RolePayPackage, RolePayPackageLine
from payroll.services import calculate_run, create_run
from payroll.starters import seed_starter_components
from utils.tests.api_test_base import SuperAdminAPITestCase


class RolePayPackageTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        self.sales_role = Role.objects.get(name=ROLE_SALES)
        self.transport = PayComponent.objects.get(code='ALLOWANCE_TRANSPORT')
        self.user = User.objects.create_user(
            username='pkg_sales',
            email='pkg.sales@example.com',
            password='x',
            first_name='Pat',
            last_name='Sales',
        )
        UserProfile.objects.create(
            user=self.user,
            role='cashier',
            custom_role=self.sales_role,
            is_active=True,
        )
        self.emp = Employee.objects.create(
            user=self.user,
            employee_id='PKG-1',
            first_name='Pat',
            last_name='Sales',
            email='pkg.sales@example.com',
            position='Sales',
            department='sales',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('20000.00'),
            created_by=self.admin,
        )
        self.package = RolePayPackage.objects.create(
            role=self.sales_role,
            name='Sales package',
            default_basic=Decimal('18000.00'),
            is_active=True,
        )
        RolePayPackageLine.objects.create(
            package=self.package,
            component=self.transport,
            amount=Decimal('2500.00'),
            is_active=True,
        )

    def test_calculate_applies_role_package(self):
        run = create_run(year=2026, month=7, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = run.payslips.get(employee=self.emp)
        self.assertEqual(slip.basic_salary, Decimal('20000.00'))
        self.assertEqual(slip.gross_pay, Decimal('22500.00'))
        self.assertEqual(slip.calculation_meta.get('role'), ROLE_SALES)

    def test_employee_assignment_overrides_package(self):
        EmployeePayAssignment.objects.create(
            employee=self.emp,
            component=self.transport,
            amount=Decimal('4000.00'),
            notes='Personal top-up',
        )
        run = create_run(year=2026, month=8, user=self.admin)
        run = calculate_run(run, user=self.admin)
        slip = run.payslips.get(employee=self.emp)
        self.assertEqual(slip.gross_pay, Decimal('24000.00'))

    def test_api_create_package(self):
        RolePayPackage.objects.filter(role=self.sales_role).delete()
        res = self.client.post(
            '/api/payroll/packages/',
            {
                'role': self.sales_role.id,
                'name': 'Sales package',
                'default_basic': '19000.00',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['role'], self.sales_role.id)
        line = self.client.post(
            f'/api/payroll/packages/{res.data["id"]}/lines/',
            {'component': self.transport.id, 'amount': '1500.00'},
            format='json',
        )
        self.assertEqual(line.status_code, 201, line.data)
        self.assertEqual(len(line.data['lines']), 1)

    def test_package_staff_lists_role_employees(self):
        staff = self.client.get(f'/api/payroll/packages/{self.package.id}/staff/')
        self.assertEqual(staff.status_code, 200, staff.data)
        self.assertEqual(staff.data['employee_count'], 1)
        self.assertEqual(staff.data['results'][0]['employee_id'], 'PKG-1')
        self.assertTrue(staff.data['results'][0]['inherits_package'])
        self.assertEqual(staff.data['results'][0]['override_count'], 0)
