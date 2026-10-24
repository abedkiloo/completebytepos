"""Employee API tests — super admin has full employees permissions."""

from datetime import date

from rest_framework import status

from employees.models import Employee
from employees.tests.test_module_settings_phase3 import _seed_employee_settings
from settings.models import ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase


class EmployeeViewsTestCase(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_employee_settings()

    def test_create_list_and_statistics(self):
        create = self.client.post(
            '/api/employees/employees/',
            {
                'employee_id': 'EMP-100',
                'first_name': 'Alice',
                'last_name': 'Okello',
                'position': 'Store Manager',
                'department': 'management',
                'hire_date': date.today().isoformat(),
                'status': 'active',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)

        listing = self.client.get('/api/employees/employees/?search=Alice')
        self.assertEqual(listing.status_code, status.HTTP_200_OK)

        stats = self.client.get('/api/employees/employees/statistics/')
        self.assertEqual(stats.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(stats.data['total_employees'], 1)

    def test_update_employee_status(self):
        employee = Employee.objects.create(
            employee_id='EMP-200',
            first_name='Bob',
            last_name='Kim',
            position='Clerk',
            department='sales',
            hire_date=date.today(),
            status='active',
            created_by=self.admin,
        )
        response = self.client.patch(
            f'/api/employees/employees/{employee.id}/',
            {'status': 'inactive'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employee.refresh_from_db()
        self.assertEqual(employee.status, 'inactive')

    def test_disabled_module_returns_empty_queryset(self):
        ModuleSettings.objects.filter(module_name='employees').update(is_enabled=False)
        response = self.client.get('/api/employees/employees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('results', response.data), [])

    def test_create_employee_from_login_user(self):
        from django.contrib.auth.models import User

        staff = User.objects.create_user(
            username='grace_hr',
            email='grace@example.com',
            password='tmp12345',
            first_name='Grace',
            last_name='HR',
        )
        linkable = self.client.get('/api/employees/employees/linkable-users/')
        self.assertEqual(linkable.status_code, status.HTTP_200_OK)
        ids = {row['id'] for row in linkable.data['results']}
        self.assertIn(staff.id, ids)

        created = self.client.post(
            '/api/employees/employees/from-user/',
            {
                'user_id': staff.id,
                'position': 'HR Officer',
                'department': 'admin',
                'hire_date': date.today().isoformat(),
                'salary': '45000.00',
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data['user'], staff.id)
        self.assertEqual(created.data['first_name'], 'Grace')
        self.assertEqual(created.data['email'], 'grace@example.com')
        self.assertTrue(created.data['employee_id'].startswith('USR-'))

        again = self.client.get('/api/employees/employees/linkable-users/')
        ids_after = {row['id'] for row in again.data['results']}
        self.assertNotIn(staff.id, ids_after)

    def test_role_filter_totals_and_id_number(self):
        from decimal import Decimal

        from django.contrib.auth.models import User

        from accounts.models import Role, UserProfile
        from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles

        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        sales = Role.objects.get(name=ROLE_SALES)

        u1 = User.objects.create_user(username='emp_sales_a', email='a@ex.com', password='x')
        UserProfile.objects.create(user=u1, role='cashier', custom_role=sales, is_active=True)
        Employee.objects.create(
            user=u1,
            employee_id='EMP-S1',
            id_number='11223344',
            first_name='Ann',
            last_name='Sales',
            email='a@ex.com',
            position='Cashier',
            department='sales',
            hire_date=date.today(),
            status='active',
            salary=Decimal('20000.00'),
            created_by=self.admin,
        )
        Employee.objects.create(
            employee_id='EMP-OTHER',
            first_name='No',
            last_name='Role',
            position='Temp',
            department='other',
            hire_date=date.today(),
            status='active',
            salary=Decimal('10000.00'),
            created_by=self.admin,
        )

        listing = self.client.get(f'/api/employees/employees/?role={sales.id}')
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        rows = listing.data.get('results', listing.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['employee_id'], 'EMP-S1')
        self.assertEqual(rows[0]['id_number'], '11223344')
        self.assertEqual(rows[0]['role_name'], ROLE_SALES)

        stats = self.client.get(f'/api/employees/employees/statistics/?role={sales.id}')
        self.assertEqual(stats.status_code, status.HTTP_200_OK)
        self.assertEqual(stats.data['total_employees'], 1)
        self.assertEqual(Decimal(str(stats.data['total_salary'])), Decimal('20000.00'))
