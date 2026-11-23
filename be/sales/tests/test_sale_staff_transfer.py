"""Move a completed sale from one salesperson to another. Admin only."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from employees.models import Employee
from payroll.adapters.commission import _staff_sale_q
from payroll.models import PayrollRun, Payslip
from sales.models import Sale
from sales.sale_staff_transfer import (
    NOTE_MAX,
    _append_note,
    _month_pay_is_locked,
    _staff_name,
    staff_choices,
    transfer_sale_staff,
    user_may_move_sale_staff,
)
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase

STAFF_PHONE = '0711666009'


def _sale(cashier, number='S-STAFF-1', served_by=None, status='completed'):
    return Sale.objects.create(
        sale_number=number,
        status=status,
        sale_type='pos',
        entry_source='pos',
        cashier=cashier,
        served_by=served_by or cashier,
        subtotal=Decimal('1500.00'),
        total=Decimal('1500.00'),
        amount_paid=Decimal('500.00'),
        payment_method='cash',
    )


class SaleStaffTransferTests(SuperAdminAPITestCase):
    """An admin moves the salesperson. A manager cannot."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        roles = sync_default_roles(created_by=self.admin)
        self.rita = User.objects.create_user('rita_sales', password='x', first_name='Rita')
        self.paul = User.objects.create_user('paul_sales', password='x', first_name='Paul')
        for person, role in ((self.rita, roles[ROLE_SALES]), (self.paul, roles[ROLE_SALES])):
            UserProfile.objects.create(
                user=person, role='cashier', custom_role=role, is_active=True,
            )
        self.manager = User.objects.create_user('move_mgr', password='x')
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=roles[ROLE_MANAGER],
            is_active=True,
        )
        ModuleSettings.objects.update_or_create(
            module_name='sales',
            defaults={'description': 'sales', 'is_enabled': True},
        )

    def _as(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_admin_move_keeps_money_and_credits_the_new_person(self):
        sale = _sale(self.rita, served_by=self.rita)
        response = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': self.paul.id, 'reason': 'Keyed on the wrong person', 'phone': STAFF_PHONE},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['to_staff_name'], 'Paul')
        self.assertIn('Salesperson moved from Rita to Paul', Sale.objects.get(pk=sale.id).notes)
        self.assertEqual(response.data['from_staff_name'], 'Rita')
        self.assertNotIn(STAFF_PHONE, str(response.data))
        sale.refresh_from_db()
        self.assertEqual(sale.cashier_id, self.paul.id)
        self.assertEqual(sale.served_by_id, self.paul.id)
        self.assertEqual(sale.total, Decimal('1500.00'))
        self.assertEqual(sale.amount_paid, Decimal('500.00'))
        self.assertEqual(sale.customer_id, None)
        self.assertFalse(Sale.objects.filter(_staff_sale_q(self.rita.id), pk=sale.id).exists())
        self.assertTrue(Sale.objects.filter(_staff_sale_q(self.paul.id), pk=sale.id).exists())

    def test_bounds_and_the_same_person_are_refused(self):
        sale = _sale(self.rita)
        same = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': self.rita.id},
            format='json',
        )
        self.assertEqual(same.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(STAFF_PHONE, str(same.data))
        long_reason = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': self.paul.id, 'reason': 'x' * 201},
            format='json',
        )
        self.assertEqual(long_reason.status_code, status.HTTP_400_BAD_REQUEST)
        sale.refresh_from_db()
        self.assertEqual(sale.cashier_id, self.rita.id)
        holding = _sale(self.rita, number='S-HOLD', status='holding')
        refused = self.client.post(
            f'/api/sales/{holding.id}/transfer-staff/',
            {'user_id': self.paul.id},
            format='json',
        )
        self.assertEqual(refused.status_code, status.HTTP_404_NOT_FOUND)
        holding.refresh_from_db()
        self.assertEqual(holding.cashier_id, self.rita.id)
        inactive = User.objects.create_user('gone_sales', password='x', is_active=False)
        UserProfile.objects.create(user=inactive, role='cashier', is_active=False)
        missing = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': inactive.id},
            format='json',
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_sales_and_anonymous_cannot_move_it(self):
        sale = _sale(self.rita, number='S-SEC')
        self._as(self.manager)
        manager = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': self.paul.id, 'phone': STAFF_PHONE},
            format='json',
        )
        self.assertEqual(manager.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(STAFF_PHONE, str(manager.data))
        self._as(self.rita)
        sales = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': self.paul.id},
            format='json',
        )
        self.assertEqual(sales.status_code, status.HTTP_403_FORBIDDEN)
        self.client.credentials()
        anon = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': self.paul.id},
            format='json',
        )
        self.assertEqual(anon.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(STAFF_PHONE, str(anon.data))
        put = self.client.put(f'/api/sales/{sale.id}/transfer-staff/', {}, format='json')
        self.assertIn(put.status_code, (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        ))
        sale.refresh_from_db()
        self.assertEqual(sale.served_by_id, self.rita.id)

    def test_feature_off_hides_the_move(self):
        module = ModuleSettings.objects.get(module_name='sales')
        feature, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='transfer_sale_staff',
            defaults={'feature_name': 'Move a sale to another salesperson', 'is_enabled': False},
        )
        feature.is_enabled = False
        feature.save(update_fields=['is_enabled'])
        try:
            sale = _sale(self.rita, number='S-OFF')
            blocked = self.client.post(
                f'/api/sales/{sale.id}/transfer-staff/',
                {'user_id': self.paul.id},
                format='json',
            )
            self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
            hidden = self.client.get('/api/sales/staff/', {'q': 'Paul'})
            self.assertEqual(hidden.status_code, status.HTTP_403_FORBIDDEN)
            self.assertNotIn(STAFF_PHONE, str(hidden.data))
            sale.refresh_from_db()
            self.assertEqual(sale.cashier_id, self.rita.id)
        finally:
            feature.is_enabled = True
            feature.save(update_fields=['is_enabled'])

    def test_a_locked_payslip_keeps_the_sale_where_it_is(self):
        sale = _sale(self.rita, number='S-LOCK')
        employee = Employee.objects.create(
            employee_id='EMP-LOCK-1',
            first_name='Rita',
            last_name='Sales',
            phone=STAFF_PHONE,
            position='Sales',
            hire_date=date(2026, 1, 1),
            user=self.rita,
        )
        today = timezone.localdate()
        run = PayrollRun.objects.create(
            year=today.year,
            month=today.month,
            status=PayrollRun.STATUS_DRAFT,
            period_start=today.replace(day=1),
            period_end=today,
        )
        Payslip.objects.create(
            run=run,
            employee=employee,
            employee_id_snapshot='EMP-LOCK-1',
            employee_name_snapshot='Rita Sales',
        )
        draft = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': self.paul.id},
            format='json',
        )
        self.assertEqual(draft.status_code, status.HTTP_200_OK, draft.data)
        sale.cashier = self.rita
        sale.served_by = self.rita
        sale.save(update_fields=['cashier', 'served_by'])
        run.status = PayrollRun.STATUS_LOCKED
        run.save(update_fields=['status'])
        locked = self.client.post(
            f'/api/sales/{sale.id}/transfer-staff/',
            {'user_id': self.paul.id},
            format='json',
        )
        self.assertEqual(locked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(STAFF_PHONE, str(locked.data))
        sale.refresh_from_db()
        self.assertEqual(sale.served_by_id, self.rita.id)

    def test_a_failed_audit_write_still_moves_the_sale(self):
        sale = _sale(self.rita, number='S-AUDIT')
        with patch(
            'utils.audit_events.log_sale_staff_transferred',
            side_effect=RuntimeError('audit down'),
        ):
            response = self.client.post(
                f'/api/sales/{sale.id}/transfer-staff/',
                {'user_id': self.paul.id},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertNotIn(STAFF_PHONE, str(response.data))
        sale.refresh_from_db()
        self.assertEqual(sale.served_by_id, self.paul.id)
        self.assertEqual(sale.amount_paid, Decimal('500.00'))

    def test_staff_search_returns_names_only(self):
        Employee.objects.create(
            employee_id='EMP-PAUL',
            first_name='Paul',
            last_name='Sales',
            phone=STAFF_PHONE,
            position='Sales',
            hire_date=date(2026, 1, 1),
            user=self.paul,
        )
        found = self.client.get('/api/sales/staff/', {'q': 'Paul'})
        self.assertEqual(found.status_code, status.HTTP_200_OK)
        self.assertIn('Paul', str(found.data))
        self.assertNotIn(STAFF_PHONE, str(found.data))
        self._as(self.manager)
        denied = self.client.get('/api/sales/staff/', {'q': 'Paul'})
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(STAFF_PHONE, str(denied.data))

    def test_forty_sales_each_land_on_the_new_person(self):
        ids = []
        for index in range(40):
            sale = _sale(self.rita, number=f'S-BULK-{index}')
            ids.append(sale.id)
            response = self.client.post(
                f'/api/sales/{sale.id}/transfer-staff/',
                {'user_id': self.paul.id},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        moved = Sale.objects.filter(id__in=ids)
        self.assertEqual(moved.count(), 40)
        self.assertTrue(all(row.cashier_id == self.paul.id and row.served_by_id == self.paul.id for row in moved))
        self.assertEqual(sum(row.total for row in moved), Decimal('60000.00'))

    def test_service_refuses_bad_ids_unfinished_sales_and_long_notes(self):
        self.assertFalse(user_may_move_sale_staff(None))
        self.assertFalse(user_may_move_sale_staff(AnonymousUser()))
        sale = _sale(self.rita, number='S-UNIT')
        with self.assertRaises(ValidationError):
            transfer_sale_staff(sale.id, self.paul.id, self.admin, reason='n' * 201)
        with self.assertRaises(ValidationError):
            transfer_sale_staff(9_999_999, self.paul.id, self.admin)
        with self.assertRaises(ValidationError):
            transfer_sale_staff('not-a-sale', self.paul.id, self.admin)
        holding = _sale(self.rita, number='S-UNIT-HOLD', status='holding')
        with self.assertRaises(ValidationError):
            transfer_sale_staff(holding.id, self.paul.id, self.admin)
        with self.assertRaises(ValidationError):
            transfer_sale_staff(sale.id, 'paul', self.admin)
        with self.assertRaises(ValidationError):
            transfer_sale_staff(sale.id, 0, self.admin)
        with self.assertRaises(PermissionDenied):
            transfer_sale_staff(sale.id, self.paul.id, self.manager)
        undated = SimpleNamespace(
            occurred_at=None, created_at=None, cashier_id=self.rita.id, served_by_id=None,
        )
        self.assertFalse(_month_pay_is_locked(undated, self.paul.id))
        sale.notes = 'old ' * 1200
        sale.served_by = None
        sale.save(update_fields=['notes', 'served_by'])
        moved = transfer_sale_staff(sale.id, self.paul.id, self.admin, reason='Counter mix-up')
        self.assertLessEqual(len(moved['sale'].notes), NOTE_MAX)
        self.assertIn('Salesperson moved from Rita to Paul', moved['sale'].notes)
        self.assertTrue(moved['sale'].notes.endswith('Reason: Counter mix-up'))
        self.assertEqual(_staff_name(None), 'Staff')
        self.assertEqual(len(_append_note('x' * 5000, None, self.paul, '')), NOTE_MAX)
        blank = staff_choices('')
        self.assertLessEqual(len(blank), 20)
        self.assertTrue(all('phone' not in row for row in blank))
        sale.refresh_from_db()
        self.assertEqual(sale.cashier_id, self.paul.id)
        self.assertEqual(sale.served_by_id, self.paul.id)
        self.assertEqual(sale.total, Decimal('1500.00'))
        self.assertEqual(sale.amount_paid, Decimal('500.00'))
