"""Employee service unit tests."""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from employees.models import Employee
from employees.services import EmployeeService


class EmployeeServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='emp_svc', password='x')
        self.service = EmployeeService()
        Employee.objects.create(
            employee_id='EMP-001',
            first_name='Jane',
            last_name='Doe',
            position='Cashier',
            department='sales',
            hire_date=date(2024, 1, 15),
            status='active',
            created_by=self.user,
        )
        Employee.objects.create(
            employee_id='EMP-002',
            first_name='John',
            last_name='Smith',
            position='Accountant',
            department='finance',
            hire_date=date(2023, 6, 1),
            status='inactive',
            created_by=self.user,
        )

    def test_build_queryset_department_filter(self):
        qs = self.service.build_queryset({'department': 'finance'})
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().employee_id, 'EMP-002')

    def test_build_queryset_search(self):
        qs = self.service.build_queryset({'search': 'Jane'})
        self.assertEqual(qs.count(), 1)

    def test_get_employee_statistics(self):
        stats = self.service.get_employee_statistics()
        self.assertEqual(stats['total_employees'], 2)
        self.assertEqual(stats['active_employees'], 1)
        self.assertEqual(stats['inactive_employees'], 1)
        departments = {row['department'] for row in stats['employees_by_department']}
        self.assertIn('sales', departments)
        self.assertIn('finance', departments)
