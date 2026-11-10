"""
End-to-end integrity: field commission vs sales visibility, reports, payroll.

Guarantees:
- Shop POS never leaks into field-agent commission or their sales list.
- Zip / cup-holder lines stay on sales views but do not inflate awards.
- Month payroll award equals the sum of daily awards (no double-count / drift).
- Month aggregation stays O(1) query sets (not one trip per calendar day).
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_FIELD_AGENT, ensure_permissions, sync_default_roles
from employees.models import Employee
from payroll.adapters.commission import fetch_sales_commission
from payroll.commission_template import DEFAULT_COMMISSION_TEMPLATE
from payroll.daily_commission import (
    agent_day_commission,
    qualifying_sales_for_user_day,
    sum_daily_commissions_for_month,
)
from payroll.models import PayrollSettings, PayslipLine
from payroll.services import calculate_run, create_run
from payroll.starters import seed_starter_components
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund, SaleRefundItem
from utils.tests.api_test_base import SuperAdminAPITestCase


class CommissionSystemIntegrityTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        seed_starter_components()
        self.field_role = Role.objects.get(name=ROLE_FIELD_AGENT)
        self.agent = User.objects.create_user(
            username='integrity_agent',
            email='integrity.agent@example.com',
            password='x',
            first_name='Ira',
            last_name='Agent',
        )
        UserProfile.objects.create(
            user=self.agent,
            role='cashier',
            custom_role=self.field_role,
            is_active=True,
        )
        self.emp = Employee.objects.create(
            user=self.agent,
            employee_id='IA-1',
            first_name='Ira',
            last_name='Agent',
            email='integrity.agent@example.com',
            position=ROLE_FIELD_AGENT,
            department='sales',
            hire_date=date(2024, 1, 1),
            status='active',
            salary=Decimal('0.00'),
            created_by=self.admin,
        )
        category = Category.objects.create(name='Integrity Cat', is_active=True)
        self.kit = Product.objects.create(
            name='Upholstery Kit',
            sku='KIT-I',
            category=category,
            price=Decimal('1000'),
            stock_quantity=200,
            track_stock=True,
            is_active=True,
        )
        self.zip = Product.objects.create(
            name='Metal Zip #5',
            sku='ZIP-I',
            category=category,
            price=Decimal('100'),
            stock_quantity=200,
            track_stock=True,
            is_active=True,
        )
        settings = PayrollSettings.load()
        settings.include_sales_commission = True
        settings.include_appraisal_bonus = False
        settings.sales_commission_template = DEFAULT_COMMISSION_TEMPLATE
        settings.save()

    def _auth_agent(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.agent)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def _sale(
        self,
        *,
        total,
        day,
        product=None,
        entry_source='field',
        paid=None,
        number=None,
        lines=None,
    ):
        product = product or self.kit
        paid = total if paid is None else paid
        sale = Sale.objects.create(
            sale_number=number or f'INT-{entry_source}-{total}-{day.isoformat()}',
            status='completed',
            sale_type='pos',
            entry_source=entry_source,
            subtotal=total,
            total=total,
            amount_paid=paid,
            payment_method='cash',
            cashier=self.agent,
            served_by=self.agent,
            occurred_at=timezone.make_aware(
                datetime(day.year, day.month, day.day, 10, 30, 0)
            ),
        )
        if lines:
            for prod, amount in lines:
                SaleItem.objects.create(
                    sale=sale,
                    product=prod,
                    quantity=1,
                    unit_price=amount,
                    subtotal=amount,
                )
        else:
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=1,
                unit_price=total,
                subtotal=total,
            )
        return sale

    def test_shop_sale_never_counts_for_commission(self):
        day = date(2026, 5, 4)
        self._sale(total=Decimal('40000.00'), day=day, entry_source='shop')
        self._sale(total=Decimal('15000.00'), day=day, entry_source='field')
        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=True
        ):
            payload = agent_day_commission(self.agent.id, day)
        self.assertEqual(payload['qualifying_sales'], '15000.00')
        self.assertEqual(payload['commission'], '500.00')
        self.assertEqual(payload['sale_count'], 1)

    def test_field_agent_sales_list_is_field_only(self):
        day = date(2026, 5, 5)
        field = self._sale(
            total=Decimal('12000.00'),
            day=day,
            entry_source='field',
            number='INT-FIELD-LIST',
        )
        shop = self._sale(
            total=Decimal('9000.00'),
            day=day,
            entry_source='shop',
            number='INT-SHOP-LIST',
        )
        # Zip still appears in the agent's field sales list.
        zip_sale = self._sale(
            total=Decimal('3000.00'),
            day=day,
            entry_source='field',
            product=self.zip,
            number='INT-ZIP-LIST',
        )
        client = self._auth_agent()
        res = client.get('/api/sales/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        results = res.data.get('results', res.data)
        ids = {row['id'] for row in results}
        self.assertIn(field.id, ids)
        self.assertIn(zip_sale.id, ids)
        self.assertNotIn(shop.id, ids)

    def test_zip_on_mixed_sale_does_not_qualify_but_refund_does_not_leak(self):
        day = date(2026, 5, 6)
        sale = self._sale(
            total=Decimal('25000.00'),
            day=day,
            number='INT-MIXED',
            lines=[
                (self.kit, Decimal('20000.00')),
                (self.zip, Decimal('5000.00')),
            ],
        )
        zip_item = sale.items.get(product=self.zip)
        refund = SaleRefund.objects.create(
            sale=sale,
            refund_type='partial',
            amount=Decimal('5000.00'),
            reason='return zip portion',
            refunded_by=self.admin,
        )
        SaleRefundItem.objects.create(
            refund=refund,
            sale_item=zip_item,
            product=self.zip,
            quantity=1,
            unit_price=Decimal('5000.00'),
            subtotal=Decimal('5000.00'),
        )
        SaleRefund.objects.filter(pk=refund.pk).update(
            created_at=timezone.make_aware(datetime(2026, 5, 6, 15, 0, 0)),
        )
        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=True
        ):
            info = qualifying_sales_for_user_day(self.agent.id, day)
        # Zip return hits the zip line only — kit 20k still qualifies in full.
        self.assertEqual(info['gross_attributed'], Decimal('20000.00'))
        self.assertEqual(info['excluded_lines'], Decimal('5000.00'))
        self.assertEqual(info['qualifying_sales'], Decimal('20000.00'))
        self.assertEqual(info['refunds'], Decimal('0.00'))

    def test_month_award_equals_sum_of_days_and_payslip(self):
        d1 = date(2026, 6, 2)
        d2 = date(2026, 6, 10)
        self._sale(total=Decimal('25000.00'), day=d1)
        self._sale(total=Decimal('15000.00'), day=d2)
        # Noise that must not change the award.
        self._sale(total=Decimal('50000.00'), day=d1, entry_source='shop')
        self._sale(total=Decimal('8000.00'), day=d2, product=self.zip)

        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=True
        ):
            day1 = agent_day_commission(self.agent.id, d1)
            day2 = agent_day_commission(self.agent.id, d2)
            month = sum_daily_commissions_for_month(
                self.agent.id, year=2026, month=6
            )
            payroll = fetch_sales_commission(self.emp, year=2026, month=6)

            expected_commission = Decimal(day1['commission']) + Decimal(
                day2['commission']
            )
            expected_transport = Decimal(day1['transport']['amount']) + Decimal(
                day2['transport']['amount']
            )
            expected_total = expected_commission + expected_transport

            self.assertEqual(month['commission_total'], expected_commission)
            self.assertEqual(month['transport_total'], expected_transport)
            self.assertEqual(month['amount'], expected_total)
            self.assertEqual(payroll['amount'], expected_total)
            self.assertEqual(len(month['days']), 2)

            run = create_run(year=2026, month=6, user=self.admin)
            run = calculate_run(run, user=self.admin)
            line = PayslipLine.objects.get(
                payslip__run=run,
                payslip__employee=self.emp,
                component__code='EARN_COMMISSION',
            )
            self.assertEqual(Decimal(line.amount), expected_total)

    def test_month_sum_uses_bounded_queries_not_per_day(self):
        for day_n in (1, 5, 10, 15, 20, 25):
            self._sale(
                total=Decimal('13000.00'),
                day=date(2026, 7, day_n),
                number=f'INT-Q-{day_n}',
            )
        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=True
        ):
            with CaptureQueriesContext(connection) as ctx:
                summary = sum_daily_commissions_for_month(
                    self.agent.id, year=2026, month=7
                )
        self.assertEqual(len(summary['days']), 6)
        # Sales load + items prefetch + refunds aggregate (+ optional settings).
        # Must stay far below 31 day trips (~60+).
        self.assertLessEqual(len(ctx.captured_queries), 12)
