"""Phase 3 — employees module settings gates."""

from datetime import date
from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from employees.models import Employee
from settings.models import ModuleSetting, ModuleSettings
from settings.settings_service import SettingsService
from utils.tests.api_test_base import SuperAdminAPITestCase


def _seed_employee_settings():
    cache.clear()
    ModuleSettings.objects.update_or_create(
        module_name='employees',
        defaults={'description': 'Employees', 'is_enabled': True},
    )
    for key, default in (
        ('show_employee_id', True),
        ('show_salary', False),
        ('show_department', True),
        ('show_contact_details', True),
        ('show_employee_notes', True),
        ('show_employee_status', True),
        ('enable_employee_create', True),
        ('enable_employee_edit', True),
        ('enable_employee_delete', True),
        ('enable_employee_statistics', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='employees',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class EmployeeModuleSettingsAPITests(SuperAdminAPITestCase):
    base_url = '/api/employees/employees/'

    def setUp(self):
        super().setUp()
        _seed_employee_settings()
        self.employee = Employee.objects.create(
            employee_id='EMP-TEST-001',
            first_name='Test',
            last_name='Worker',
            position='Cashier',
            department='sales',
            hire_date=date.today(),
            status='active',
            salary=Decimal('45000.00'),
            email='worker@test.com',
        )

    def test_create_forbidden_when_disabled(self):
        SettingsService.set('employees', 'enable_employee_create', False)
        response = self.client.post(
            self.base_url,
            {
                'employee_id': 'EMP-NEW',
                'first_name': 'New',
                'last_name': 'Hire',
                'position': 'Clerk',
                'hire_date': '2024-01-01',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_statistics_forbidden_when_disabled(self):
        SettingsService.set('employees', 'enable_employee_statistics', False)
        response = self.client.get(f'{self.base_url}statistics/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_omits_salary_when_hidden(self):
        SettingsService.set('employees', 'show_salary', False)
        response = self.client.get(f'{self.base_url}{self.employee.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('salary', response.data)
