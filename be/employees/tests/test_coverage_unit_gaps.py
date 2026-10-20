"""Focused unit/API coverage for employees helpers and view edge paths."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status

from employees.models import Employee
from employees.module_settings import (
    apply_employee_representation_flags,
    employees_enable_create,
    employees_enable_delete,
    employees_enable_edit,
    employees_enable_statistics,
    employees_show_employee_id,
    validate_employee_write,
)
from employees.serializers import EmployeeSerializer
from employees.services import EmployeeService
from employees.tests.test_module_settings_phase3 import _seed_employee_settings
from settings.settings_service import SettingsService
from utils.tests.api_test_base import SalesAPITestCase, SuperAdminAPITestCase


class EmployeeModuleSettingsUnitTests(TestCase):
    def setUp(self):
        cache.clear()
        _seed_employee_settings()

    def test_representation_and_write_flags_strip_fields_and_defaults(self):
        for key in (
            'show_employee_id',
            'show_salary',
            'show_department',
            'show_contact_details',
            'show_employee_notes',
            'show_employee_status',
        ):
            SettingsService.set('employees', key, False)

        data = apply_employee_representation_flags({
            'employee_id': 'E1',
            'salary': '100',
            'department': 'sales',
            'email': 'a@t.com',
            'phone': '0700',
            'address': 'St',
            'notes': 'n',
            'status': 'active',
            'is_active': True,
        })
        for key in (
            'employee_id', 'salary', 'department', 'email', 'phone',
            'address', 'notes', 'status', 'is_active',
        ):
            self.assertNotIn(key, data)

        attrs = validate_employee_write({})
        self.assertEqual(attrs['department'], 'other')
        self.assertEqual(attrs['status'], 'active')

        self.assertFalse(employees_show_employee_id())
        SettingsService.set('employees', 'enable_employee_create', False)
        self.assertFalse(employees_enable_create())
        SettingsService.set('employees', 'enable_employee_edit', False)
        self.assertFalse(employees_enable_edit())
        SettingsService.set('employees', 'enable_employee_delete', False)
        self.assertFalse(employees_enable_delete())
        SettingsService.set('employees', 'enable_employee_statistics', False)
        self.assertFalse(employees_enable_statistics())


class EmployeeSerializerUnitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('emp_unit', password='x')
        Employee.objects.create(
            employee_id='EMP-DUP',
            first_name='Existing',
            last_name='Worker',
            position='Clerk',
            department='sales',
            hire_date=date.today(),
            status='active',
            created_by=self.user,
        )

    def test_duplicate_employee_id_on_create_and_update(self):
        ser = EmployeeSerializer(
            data={
                'employee_id': 'EMP-DUP',
                'first_name': 'New',
                'last_name': 'Hire',
                'position': 'Clerk',
                'hire_date': date.today().isoformat(),
            },
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('employee_id', ser.errors)

        existing = Employee.objects.get(employee_id='EMP-DUP')
        update = EmployeeSerializer(
            instance=existing,
            data={
                'employee_id': 'EMP-DUP',
                'first_name': 'Existing',
                'last_name': 'Worker',
                'position': 'Clerk',
                'hire_date': date.today().isoformat(),
            },
            partial=True,
        )
        self.assertTrue(update.is_valid(), update.errors)

        other = Employee.objects.create(
            employee_id='EMP-OTHER',
            first_name='Other',
            last_name='Person',
            position='Clerk',
            department='sales',
            hire_date=date.today(),
            status='active',
        )
        clash = EmployeeSerializer(
            instance=existing,
            data={'employee_id': other.employee_id},
            partial=True,
        )
        self.assertFalse(clash.is_valid())
        self.assertIn('employee_id', clash.errors)

    def test_email_and_phone_validation(self):
        ser = EmployeeSerializer(
            data={
                'employee_id': 'EMP-VAL',
                'first_name': 'Val',
                'last_name': 'Idation',
                'position': 'Clerk',
                'hire_date': date.today().isoformat(),
                'email': 'not-an-email',
                'phone': 'bad-phone',
            },
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('email', ser.errors)

        ok = EmployeeSerializer(
            data={
                'employee_id': 'EMP-OK',
                'first_name': 'Val',
                'last_name': 'Idation',
                'position': 'Clerk',
                'hire_date': date.today().isoformat(),
                'email': '  ok@test.com  ',
            },
        )
        self.assertTrue(ok.is_valid(), ok.errors)
        self.assertEqual(ok.validated_data['email'], 'ok@test.com')


class EmployeeServiceUnitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('emp_svc2', password='x')
        Employee.objects.create(
            employee_id='EMP-ST',
            first_name='Status',
            last_name='Filter',
            position='Clerk',
            department='sales',
            hire_date=date.today(),
            status='inactive',
            created_by=self.user,
        )

    def test_build_queryset_status_filter(self):
        qs = EmployeeService().build_queryset({'status': 'inactive'})
        self.assertEqual(qs.count(), 1)


class EmployeeCoverageAPITests(SuperAdminAPITestCase):
    base_url = '/api/employees/employees/'

    def setUp(self):
        super().setUp()
        _seed_employee_settings()
        self.employee = Employee.objects.create(
            employee_id='EMP-COV',
            first_name='Cov',
            last_name='Worker',
            position='Clerk',
            department='sales',
            hire_date=date.today(),
            status='active',
            salary=Decimal('30000.00'),
        )

    def test_edit_and_delete_forbidden_when_disabled(self):
        SettingsService.set('employees', 'enable_employee_edit', False)
        response = self.client.put(
            f'{self.base_url}{self.employee.id}/',
            {
                'employee_id': self.employee.employee_id,
                'first_name': self.employee.first_name,
                'last_name': self.employee.last_name,
                'position': self.employee.position,
                'hire_date': self.employee.hire_date.isoformat(),
                'notes': 'blocked',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.patch(
            f'{self.base_url}{self.employee.id}/',
            {'notes': 'blocked'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        SettingsService.set('employees', 'enable_employee_edit', True)
        SettingsService.set('employees', 'enable_employee_delete', False)
        response = self.client.delete(f'{self.base_url}{self.employee.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_destroy_when_enabled(self):
        doomed = Employee.objects.create(
            employee_id='EMP-DEL',
            first_name='Del',
            last_name='Me',
            position='Clerk',
            department='sales',
            hire_date=date.today(),
            status='active',
        )
        response = self.client.delete(f'{self.base_url}{doomed.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_statistics_service_error_returns_500(self):
        with patch.object(
            EmployeeService,
            'get_employee_statistics',
            side_effect=RuntimeError('emp stats failed'),
        ):
            response = self.client.get(f'{self.base_url}statistics/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)


class EmployeeStatisticsAccessAPITests(SalesAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_employee_settings()

    def test_statistics_empty_when_user_lacks_module_access(self):
        response = self.client.get('/api/employees/employees/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_employees'], 0)
