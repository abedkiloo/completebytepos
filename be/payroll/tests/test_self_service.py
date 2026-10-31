from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_SALES,
    ensure_permissions,
    grant_payroll_view_own_to_all_roles,
    sync_default_roles,
)
from employees.models import Employee
from payroll.models import PayrollSettings
from payroll.models import RolePayPackage, RolePayPackageLine, PayComponent
from payroll.services import approve_and_lock, calculate_run, create_run, submit_run
from payroll.starters import seed_starter_components
from settings.models import StoreSettings
from utils.tests.api_test_base import SuperAdminAPITestCase


class EmployeeMyPaySelfServiceTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        grant_payroll_view_own_to_all_roles()

        sales_role = Role.objects.get(name=ROLE_SALES)
        self.staff_user = User.objects.create_user(
            username='pay_staff',
            email='pay.staff@example.com',
            password='test-pass-123',
            first_name='Pat',
            last_name='Pay',
        )
        UserProfile.objects.create(
            user=self.staff_user,
            role='cashier',
            custom_role=sales_role,
            is_active=True,
        )
        self.emp = Employee.objects.create(
            user=self.staff_user,
            employee_id='PAY-1',
            first_name='Pat',
            last_name='Pay',
            email='pay.staff@example.com',
            position='Sales Personnel',
            department='sales',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('20000.00'),
            created_by=self.admin,
        )
        package = RolePayPackage.objects.create(
            role=sales_role,
            name='Sales package',
            default_basic=Decimal('18000.00'),
            is_active=True,
        )
        RolePayPackageLine.objects.create(
            package=package,
            component=PayComponent.objects.get(code='ALLOWANCE_TRANSPORT'),
            amount=Decimal('2500.00'),
            is_active=True,
        )
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff_user)

    def test_employee_sees_current_pay_estimate(self):
        res = self.staff_client.get('/api/payroll/me/pay/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['linked'])
        self.assertEqual(res.data['employee']['employee_id'], 'PAY-1')
        self.assertEqual(res.data['effective_basic'], '20000.00')
        self.assertEqual(res.data['estimated_gross'], '22500.00')
        self.assertEqual(res.data['package_name'], 'Sales package')
        self.assertTrue(res.data['inherits_package'])
        codes = {row['code'] for row in res.data['earnings']}
        self.assertIn('BASIC', codes)
        self.assertIn('ALLOWANCE_TRANSPORT', codes)

    def test_unlinked_user_gets_empty_pay_payload(self):
        orphan = User.objects.create_user(
            username='orphan_pay',
            email='orphan.pay@example.com',
            password='x',
        )
        UserProfile.objects.create(
            user=orphan,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        client = APIClient()
        client.force_authenticate(user=orphan)
        res = client.get('/api/payroll/me/pay/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data['linked'])


class EmployeePayslipSelfServiceTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        grant_payroll_view_own_to_all_roles()

        sales_role = Role.objects.get(name=ROLE_SALES)
        self.staff_user = User.objects.create_user(
            username='slip_staff',
            email='slip.staff@example.com',
            password='test-pass-123',
            first_name='Sam',
            last_name='Staff',
        )
        UserProfile.objects.create(
            user=self.staff_user,
            role='cashier',
            custom_role=sales_role,
            is_active=True,
        )
        self.emp = Employee.objects.create(
            user=self.staff_user,
            employee_id='SLIP-1',
            first_name='Sam',
            last_name='Staff',
            email='slip.staff@example.com',
            position='Clerk',
            department='sales',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('30000.00'),
            created_by=self.admin,
        )
        ps = PayrollSettings.load()
        ps.letterhead_line = 'HR Confidential — Omuwenga'
        ps.save(update_fields=['letterhead_line'])

        store = StoreSettings.load()
        store.store_name = 'Omuwenga Test Store'
        store.receipt_header_text = 'Official payslip letterhead'
        store.receipt_show_logo = True
        store.save()

        run = create_run(year=2026, month=9, user=self.admin)
        run = calculate_run(run, user=self.admin)
        run = submit_run(run, user=self.admin)
        self.run = approve_and_lock(run, user=self.admin)
        self.slip = self.run.payslips.get(employee=self.emp)

        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff_user)

    def test_draft_payslip_hidden_until_calculated(self):
        draft = create_run(year=2026, month=8, user=self.admin)
        res = self.staff_client.get('/api/payroll/me/payslips/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        periods = {row['period'] for row in res.data}
        self.assertIn(self.run.period_label, periods)
        self.assertNotIn(draft.period_label, periods)

        calculate_run(draft, user=self.admin)
        res = self.staff_client.get('/api/payroll/me/payslips/')
        periods = {row['period'] for row in res.data}
        self.assertIn(draft.period_label, periods)
        calculated = next(row for row in res.data if row['period'] == draft.period_label)
        self.assertEqual(calculated['run_status'], 'calculated')

    def test_employee_lists_and_downloads_branded_pdf(self):
        res = self.staff_client.get('/api/payroll/me/payslips/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], self.slip.id)
        self.assertEqual(res.data[0]['net_pay'], '30000.00')

        self.assertEqual(res.data[0]['filename'], 'Sam_Staff_September_2026_SLIP-1.pdf')

        pdf = self.staff_client.get(f'/api/payroll/me/payslips/{self.slip.id}/pdf/')
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertIn('inline', pdf['Content-Disposition'])
        self.assertIn(
            'Sam_Staff_September_2026_SLIP-1.pdf',
            pdf['Content-Disposition'],
        )
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertGreater(len(pdf.content), 500)

        # Branding helpers resolve configured store + payroll letterhead.
        from payroll.pdf import _payslip_letterhead
        from utils.document_branding import brand_header_text, brand_name_line

        self.assertEqual(brand_name_line(), 'Omuwenga Test Store')
        self.assertEqual(brand_header_text(), 'Official payslip letterhead')
        self.assertIn(
            'HR Confidential',
            _payslip_letterhead(PayrollSettings.load(), self.run.tenant),
        )

    def test_employee_cannot_download_other_payslip(self):
        other = Employee.objects.create(
            employee_id='SLIP-2',
            first_name='Other',
            last_name='Person',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('20000.00'),
            created_by=self.admin,
        )
        # Recalculate is blocked on locked run — create a fresh locked slip for other
        run = create_run(year=2026, month=7, user=self.admin)
        # Only other employee for July by deactivating Sam temporarily
        self.emp.status = 'inactive'
        self.emp.save(update_fields=['status'])
        run = calculate_run(run, user=self.admin)
        run = submit_run(run, user=self.admin)
        run = approve_and_lock(run, user=self.admin)
        other_slip = run.payslips.get(employee=other)
        self.emp.status = 'active'
        self.emp.save(update_fields=['status'])

        pdf = self.staff_client.get(f'/api/payroll/me/payslips/{other_slip.id}/pdf/')
        self.assertEqual(pdf.status_code, status.HTTP_403_FORBIDDEN)
