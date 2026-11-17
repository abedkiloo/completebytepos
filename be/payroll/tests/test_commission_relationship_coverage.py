"""Commission paths that reports and payroll share: refunds, rates, and a closed flag."""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_FIELD_AGENT, ensure_permissions, sync_default_roles
from employees.models import Employee
from payroll.adapters.commission import (
    _as_rate,
    ensure_field_sales_commission_package,
    fetch_sales_commission,
    net_field_sales_for_user,
    resolve_commission_rate,
    sales_commission_enabled,
)
from payroll.commission_template import normalize_commission_template
from payroll.daily_commission import (
    _refund_hit_on_qualifying,
    fetch_employee_daily_band_commission,
    load_commission_template,
    qualifying_sales_for_user_day,
    save_commission_template,
)
from payroll.models import PayComponent, PayrollSettings, RolePayPackageLine
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund, SaleRefundItem
from utils.tests.api_test_base import SuperAdminAPITestCase

COMMISSION_CODE = 'EARN_COMMISSION'


class CommissionRelationshipTests(SuperAdminAPITestCase):
    """Refunds, rate order, and a switched-off commission stay correct."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        self.package = ensure_field_sales_commission_package()
        self.role = Role.objects.get(name=ROLE_FIELD_AGENT)
        self.user = User.objects.create_user('comm_rel', password='x', email='comm.rel@example.com')
        UserProfile.objects.create(user=self.user, role='cashier', custom_role=self.role, is_active=True)
        self.employee = Employee.objects.create(
            user=self.user,
            employee_id='CR-1',
            first_name='Cora',
            last_name='Reed',
            email='comm.rel@example.com',
            position=ROLE_FIELD_AGENT,
            department='sales',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('15000.00'),
            created_by=self.admin,
        )
        self.settings = PayrollSettings.load()
        self.settings.include_sales_commission = True
        self.settings.save(update_fields=['include_sales_commission'])

    def _field_sale(self, total, day):
        """
        Save one paid field sale for the commission user.

        Args:
            total: Sale total, 0.01 through 1000000.
            day: Local date in the month under test.

        Returns:
            Sale: Completed field sale.

        Raises:
            None.
        """
        return Sale.objects.create(
            sale_number=f'CR-{total}-{day.day}-{Sale.objects.count()}',
            status='completed',
            sale_type='pos',
            entry_source='field',
            subtotal=total,
            total=total,
            amount_paid=total,
            payment_method='cash',
            cashier=self.user,
            served_by=self.user,
            occurred_at=timezone.make_aware(datetime(day.year, day.month, day.day, 11, 0, 0)),
        )

    def test_a_refund_larger_than_the_sale_floors_commission_at_zero(self):
        day = date(2026, 3, 4)
        sale = self._field_sale(Decimal('100.00'), day)
        refund = SaleRefund.objects.create(
            sale=sale,
            refund_type='full',
            amount=Decimal('150.00'),
            reason='Returned',
            refunded_by=self.admin,
        )
        SaleRefund.objects.filter(pk=refund.pk).update(created_at=sale.occurred_at)
        net = net_field_sales_for_user(self.user.id, year=2026, month=3)
        self.assertEqual(net, Decimal('0.00'))

    def test_a_bad_rate_is_zero_and_the_package_rate_is_used(self):
        self.assertEqual(_as_rate('not-a-rate'), Decimal('0.0000'))
        rate, source = resolve_commission_rate(self.employee)
        self.assertEqual(source, 'role_package')
        self.assertGreater(rate, 0)

    def test_the_component_default_is_used_when_there_is_no_package_line(self):
        RolePayPackageLine.objects.filter(package=self.package, component__code=COMMISSION_CODE).delete()
        component = PayComponent.objects.get(code=COMMISSION_CODE)
        component.default_rate = Decimal('0.0200')
        component.save(update_fields=['default_rate'])
        rate, source = resolve_commission_rate(self.employee)
        self.assertEqual(source, 'component_default')
        self.assertEqual(rate, Decimal('0.0200'))
        component.default_rate = Decimal('0')
        component.save(update_fields=['default_rate'])
        rate, source = resolve_commission_rate(self.employee)
        self.assertEqual((rate, source), (Decimal('0.0000'), 'none'))

    def test_a_closed_commission_and_a_missing_login_pay_nothing(self):
        self.settings.include_sales_commission = False
        self.settings.save(update_fields=['include_sales_commission'])
        closed = fetch_sales_commission(self.employee, year=2026, month=3)
        self.assertFalse(closed['meta']['available'])
        self.assertEqual(closed['amount'], Decimal('0.00'))
        bands = fetch_employee_daily_band_commission(self.employee, year=2026, month=3)
        self.assertEqual(bands['meta']['reason'], 'commission_disabled')

        self.settings.include_sales_commission = True
        self.settings.sales_commission_template = {'scheme': 'percent'}
        self.settings.save(update_fields=['include_sales_commission', 'sales_commission_template'])
        try:
            not_bands = fetch_employee_daily_band_commission(self.employee, year=2026, month=3)
            self.assertEqual(not_bands['meta']['reason'], 'not_daily_bands')
            self.employee.user = None
            self.employee.email = ''
            self.employee.save(update_fields=['user', 'email'])
            missing = fetch_sales_commission(self.employee, year=2026, month=3)
            self.assertEqual(missing['meta']['reason'], 'no_user')
        finally:
            self.settings.sales_commission_template = {}
            self.settings.save(update_fields=['sales_commission_template'])

    def test_a_quiet_day_and_a_line_refund_change_the_qualifying_total(self):
        quiet = qualifying_sales_for_user_day(self.user.id, date(2026, 1, 2))
        self.assertEqual(quiet['sale_count'], 0)
        day = date(2026, 5, 6)
        category = Category.objects.create(name='Comm rel', is_active=True)
        timber = Product.objects.create(
            name='Plain board', sku='CR-BOARD', category=category,
            price=Decimal('80'), stock_quantity=10, track_stock=True, is_active=True,
        )
        zipper = Product.objects.create(
            name='Heavy duty zip', sku='CR-ZIP', category=category,
            price=Decimal('20'), stock_quantity=10, track_stock=True, is_active=True,
        )
        sale = self._field_sale(Decimal('100.00'), day)
        board = SaleItem.objects.create(
            sale=sale, product=timber, quantity=1, unit_price=Decimal('80.00'), subtotal=Decimal('80.00'),
        )
        SaleItem.objects.create(
            sale=sale, product=zipper, quantity=1, unit_price=Decimal('20.00'), subtotal=Decimal('20.00'),
        )
        refund = SaleRefund.objects.create(
            sale=sale, refund_type='partial', amount=Decimal('80.00'),
            reason='Board returned', refunded_by=self.admin,
        )
        SaleRefundItem.objects.create(
            refund=refund, sale_item=board, product=timber, quantity=1,
            unit_price=Decimal('80.00'), subtotal=Decimal('80.00'),
        )
        SaleRefund.objects.filter(pk=refund.pk).update(created_at=sale.occurred_at)
        scored = qualifying_sales_for_user_day(self.user.id, day)
        self.assertEqual(scored['qualifying_sales'], Decimal('0.00'))
        self.assertEqual(scored['refunds'], Decimal('80.00'))

    def test_a_sale_level_refund_is_shared_across_the_lines(self):
        template = normalize_commission_template(None)
        day = date(2026, 5, 8)
        category = Category.objects.create(name='Share rel', is_active=True)
        timber = Product.objects.create(
            name='Plain plank', sku='CR-PLANK', category=category,
            price=Decimal('50'), stock_quantity=10, track_stock=True, is_active=True,
        )
        sale = self._field_sale(Decimal('50.00'), day)
        SaleItem.objects.create(
            sale=sale, product=timber, quantity=1, unit_price=Decimal('50.00'), subtotal=Decimal('50.00'),
        )
        refund = SaleRefund.objects.create(
            sale=sale, refund_type='partial', amount=Decimal('10.00'),
            reason='Goodwill', refunded_by=self.admin,
        )
        SaleRefund.objects.filter(pk=refund.pk).update(created_at=sale.occurred_at)
        scored = qualifying_sales_for_user_day(self.user.id, day, template=template)
        self.assertEqual(scored['qualifying_sales'], Decimal('40.00'))

    def test_a_broken_refund_list_does_not_raise(self):
        template = normalize_commission_template(None)

        class Broken:
            def all(self):
                raise RuntimeError('unread')

        sale = SimpleNamespace(refunds=Broken())
        hit = _refund_hit_on_qualifying(
            sale, Decimal('10.00'), Decimal('40.00'), Decimal('10.00'), template=template,
        )
        self.assertEqual(hit, Decimal('8.00'))
        refund = SimpleNamespace(items=Broken())
        sale.refunds = SimpleNamespace(all=lambda: [refund])
        hit = _refund_hit_on_qualifying(
            sale, Decimal('10.00'), Decimal('40.00'), Decimal('0.00'), template=template,
        )
        self.assertEqual(hit, Decimal('10.00'))

    def test_the_template_round_trip_rejects_a_list(self):
        saved = save_commission_template({'scheme': 'daily_bands'})
        self.assertEqual(saved['scheme'], 'daily_bands')
        self.assertEqual(load_commission_template()['scheme'], 'daily_bands')
        with self.assertRaises(ValueError):
            save_commission_template(['nope'])

    def test_a_settings_failure_turns_commission_off_and_a_missing_role_is_refused(self):
        with patch('settings.module_features.is_module_feature_enabled', side_effect=RuntimeError('off')):
            self.assertTrue(sales_commission_enabled())
        with patch('payroll.models.PayrollSettings.load', side_effect=RuntimeError('down')):
            self.assertFalse(sales_commission_enabled())
            self.assertEqual(load_commission_template()['scheme'], 'daily_bands')
        with patch('accounts.models.Role.objects.filter') as filtered:
            filtered.return_value.first.return_value = None
            with self.assertRaises(LookupError):
                ensure_field_sales_commission_package()

    def test_an_inactive_package_and_a_blank_rate_are_filled_in(self):
        self.package.is_active = False
        self.package.save(update_fields=['is_active', 'updated_at'])
        line = RolePayPackageLine.objects.get(package=self.package, component__code=COMMISSION_CODE)
        RolePayPackageLine.objects.filter(pk=line.pk).update(rate=None, is_active=False)
        line.refresh_from_db()
        self.assertIsNone(line.rate)
        restored = ensure_field_sales_commission_package(default_rate=Decimal('0.0400'))
        line.refresh_from_db()
        restored.refresh_from_db()
        self.assertTrue(restored.is_active)
        self.assertEqual(line.rate, Decimal('0.0300'))
        self.assertTrue(line.is_active)
