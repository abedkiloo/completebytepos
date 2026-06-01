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
