from datetime import date
from decimal import Decimal

from rest_framework import status

from accounts.role_definitions import ensure_permissions, sync_default_roles
from employees.models import Employee
from payroll.models import PayrollRun, Payslip
from payroll.services import (
    PayrollError,
    approve_and_lock,
    calculate_run,
    create_run,
    submit_run,
)
from payroll.starters import seed_starter_components
from utils.tests.api_test_base import SuperAdminAPITestCase


class PayrollWorkflowTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        self.emp = Employee.objects.create(
            employee_id='PAY-001',
            first_name='Pay',
            last_name='Tester',
            email='pay.tester@example.com',
            position='Clerk',
            department='admin',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('40000.00'),
            created_by=self.admin,
        )

    def test_full_run_lifecycle(self):
        run = create_run(year=2026, month=3, user=self.admin)
        self.assertEqual(run.status, PayrollRun.STATUS_DRAFT)

        run = calculate_run(run, user=self.admin)
        self.assertEqual(run.status, PayrollRun.STATUS_CALCULATED)
        self.assertEqual(run.employee_count, 1)
        slip = Payslip.objects.get(run=run, employee=self.emp)
        self.assertEqual(slip.basic_salary, Decimal('40000.00'))
        self.assertEqual(slip.net_pay, Decimal('40000.00'))

        run = submit_run(run, user=self.admin)
        self.assertEqual(run.status, PayrollRun.STATUS_PENDING_APPROVAL)

        run = approve_and_lock(run, user=self.admin)
        self.assertEqual(run.status, PayrollRun.STATUS_LOCKED)
        self.assertIsNotNone(run.locked_at)

        with self.assertRaises(PayrollError):
            calculate_run(run, user=self.admin)

    def test_api_create_calculate_approve(self):
        create = self.client.post(
            '/api/payroll/runs/',
            {'year': 2026, 'month': 4, 'notes': 'April'},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        run_id = create.data['id']

        calc = self.client.post(f'/api/payroll/runs/{run_id}/calculate/')
        self.assertEqual(calc.status_code, status.HTTP_200_OK, calc.data)
        self.assertEqual(calc.data['status'], 'calculated')
        self.assertEqual(calc.data['employee_count'], 1)

        submit = self.client.post(f'/api/payroll/runs/{run_id}/submit/')
        self.assertEqual(submit.status_code, status.HTTP_200_OK, submit.data)

        approve = self.client.post(f'/api/payroll/runs/{run_id}/approve/')
        self.assertEqual(approve.status_code, status.HTTP_200_OK, approve.data)
        self.assertEqual(approve.data['status'], 'locked')

        slips = self.client.get(f'/api/payroll/runs/{run_id}/payslips/')
        self.assertEqual(slips.status_code, status.HTTP_200_OK)
        self.assertEqual(len(slips.data), 1)

        pdf = self.client.get(f'/api/payroll/payslips/{slips.data[0]["id"]}/pdf/')
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_settings_and_components(self):
        settings = self.client.get('/api/payroll/settings/')
        self.assertEqual(settings.status_code, status.HTTP_200_OK)
        self.assertFalse(settings.data['statutory_enabled'])

        comps = self.client.get('/api/payroll/components/?page_size=100')
        self.assertEqual(comps.status_code, status.HTTP_200_OK)
        rows = comps.data.get('results', comps.data)
        codes = {c['code'] for c in rows}
        self.assertIn('BASIC', codes)
        self.assertIn('BONUS_APPRAISAL', codes)
