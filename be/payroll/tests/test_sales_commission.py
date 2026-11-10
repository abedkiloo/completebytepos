"""Field sales commission on payroll runs."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_FIELD_AGENT, ensure_permissions, sync_default_roles
from employees.models import Employee
from payroll.adapters.commission import (
    COMMISSION_CODE,
    ensure_field_sales_commission_package,
    fetch_sales_commission,
    net_field_sales_for_user,
)
from payroll.models import (
    EmployeePayAssignment,
    PayComponent,
    PayrollSettings,
    RolePayPackageLine,
)
from payroll.services import calculate_run, create_run
from payroll.starters import seed_starter_components
from products.models import Category, Product
from sales.models import Sale, SaleItem
from utils.tests.api_test_base import SuperAdminAPITestCase


class SalesCommissionTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        self.field_role = Role.objects.get(name=ROLE_FIELD_AGENT)
        self.package = ensure_field_sales_commission_package(
            default_rate=Decimal('0.0300'),
            default_basic=Decimal('15000.00'),
        )
        self.user = User.objects.create_user(
            username='field_comm',
            email='field.comm@example.com',
            password='x',
            first_name='Faye',
            last_name='Field',
        )
        UserProfile.objects.create(
            user=self.user,
            role='cashier',
            custom_role=self.field_role,
            is_active=True,
        )
        self.emp = Employee.objects.create(
            user=self.user,
            employee_id='FC-1',
            first_name='Faye',
            last_name='Field',
            email='field.comm@example.com',
            position=ROLE_FIELD_AGENT,
            department='sales',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('15000.00'),
            created_by=self.admin,
        )
        category = Category.objects.create(name='Comm Cat', is_active=True)
        self.product = Product.objects.create(
            name='Field Widget',
            sku='FW-1',
            category=category,
            price=Decimal('1000'),
            stock_quantity=100,
            track_stock=True,
            is_active=True,
        )
        settings = PayrollSettings.load()
        settings.include_sales_commission = True
        settings.include_appraisal_bonus = False
        settings.save()

    def _field_sale(self, *, total, day):
        sale = Sale.objects.create(
            sale_number=f'S-FIELD-{total}-{day.day}',
            status='completed',
            sale_type='pos',
            entry_source='field',
            subtotal=total,
            total=total,
            amount_paid=total,
            payment_method='cash',
            cashier=self.user,
            served_by=self.user,
            occurred_at=timezone.make_aware(datetime(day.year, day.month, day.day, 12, 0, 0)),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=total,
            subtotal=total,
        )
        return sale

    def test_daily_bands_sum_for_month(self):
        # PDF default: 50k+ → 4,000 commission + 200 transport per day.
        self._field_sale(total=Decimal('100000.00'), day=date(2026, 6, 10))
        self._field_sale(total=Decimal('50000.00'), day=date(2026, 6, 15))
        # Shop sale must not count
        Sale.objects.create(
            sale_number='S-SHOP-1',
            status='completed',
            sale_type='pos',
            entry_source='pos',
            subtotal=Decimal('99999'),
            total=Decimal('99999'),
            amount_paid=Decimal('99999'),
            payment_method='cash',
            cashier=self.user,
            served_by=self.user,
            occurred_at=timezone.make_aware(datetime(2026, 6, 12, 10, 0, 0)),
        )
        base = net_field_sales_for_user(self.user.id, year=2026, month=6)
        self.assertEqual(base, Decimal('150000.00'))
        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=True
        ):
            result = fetch_sales_commission(self.emp, year=2026, month=6)
        self.assertEqual(result['meta'].get('scheme'), 'daily_bands')
        # Two qualifying days × (4000 + 200)
        self.assertEqual(result['amount'], Decimal('8400.00'))
        self.assertEqual(result['meta']['commission_total'], '8000.00')
        self.assertEqual(result['meta']['transport_total'], '400.00')

    def test_legacy_percent_scheme_still_honours_person_rate(self):
        settings = PayrollSettings.load()
        settings.sales_commission_template = {
            'scheme': 'percent',
            'percent_rate': '0.03',
        }
        settings.save(update_fields=['sales_commission_template', 'updated_at'])
        self._field_sale(total=Decimal('100000.00'), day=date(2026, 7, 5))
        EmployeePayAssignment.objects.create(
            employee=self.emp,
            component=PayComponent.objects.get(code=COMMISSION_CODE),
            rate=Decimal('0.0500'),
            is_active=True,
            notes='Star agent',
        )
        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=True
        ):
            result = fetch_sales_commission(self.emp, year=2026, month=7)
        self.assertEqual(result['amount'], Decimal('5000.00'))
        self.assertEqual(result['meta']['rate_source'], 'assignment')

    def test_calculate_run_adds_daily_band_commission_line(self):
        self._field_sale(total=Decimal('200000.00'), day=date(2026, 8, 8))
        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=True
        ):
            run = create_run(year=2026, month=8, user=self.admin)
            run = calculate_run(run, user=self.admin)
        slip = run.payslips.get(employee=self.emp)
        line = slip.lines.filter(component__code=COMMISSION_CODE).first()
        self.assertIsNotNone(line)
        # One day at 50k+ band: 4000 commission + 200 transport
        self.assertEqual(line.amount, Decimal('4200.00'))
        self.assertIn('commission', slip.calculation_meta.get('adapters') or {})

    def test_feature_off_blocks_commission(self):
        self._field_sale(total=Decimal('100000.00'), day=date(2026, 9, 1))
        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=False
        ):
            result = fetch_sales_commission(self.emp, year=2026, month=9)
        self.assertEqual(result['amount'], Decimal('0.00'))
        self.assertEqual(result['meta'].get('reason'), 'commission_disabled')

    def test_ensure_package_idempotent(self):
        again = ensure_field_sales_commission_package()
        self.assertEqual(again.id, self.package.id)
        lines = RolePayPackageLine.objects.filter(
            package=again, component__code=COMMISSION_CODE
        )
        self.assertEqual(lines.count(), 1)
