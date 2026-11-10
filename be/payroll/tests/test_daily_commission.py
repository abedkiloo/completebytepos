"""Daily-band commission template and agent day dashboard."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_FIELD_AGENT, ensure_permissions, sync_default_roles
from payroll.commission_template import (
    DEFAULT_COMMISSION_TEMPLATE,
    commission_for_qualifying_sales,
    normalize_commission_template,
    product_name_excluded,
)
from payroll.daily_commission import agent_day_commission
from payroll.models import PayrollSettings
from products.models import Category, Product
from sales.models import Sale, SaleItem
from utils.tests.api_test_base import ManagerAPITestCase


class DailyBandUnitTests(ManagerAPITestCase):
    def test_product_exclusions_are_commission_only_and_configurable(self):
        default = normalize_commission_template(None)
        self.assertTrue(default['exclude_products_from_commission'])
        self.assertTrue(product_name_excluded('Heavy duty zip', default))
        self.assertTrue(product_name_excluded('Sofa cup holder set', default))
        self.assertFalse(product_name_excluded('Foam cushion', default))

        off = normalize_commission_template(
            {**default, 'exclude_products_from_commission': False}
        )
        self.assertFalse(product_name_excluded('Heavy duty zip', off))

        cleared = normalize_commission_template(
            {**default, 'exclude_product_keywords': []}
        )
        self.assertEqual(cleared['exclude_product_keywords'], [])
        self.assertFalse(product_name_excluded('Heavy duty zip', cleared))

        custom = normalize_commission_template(
            {
                **default,
                'exclude_product_keywords': 'foam, thread',
            }
        )
        self.assertEqual(custom['exclude_product_keywords'], ['foam', 'thread'])
        self.assertTrue(product_name_excluded('Upholstery foam', custom))
        self.assertFalse(product_name_excluded('Heavy duty zip', custom))

    def test_default_bands_match_pdf(self):
        tpl = normalize_commission_template(None)
        self.assertEqual(tpl['scheme'], 'daily_bands')
        self.assertEqual(
            commission_for_qualifying_sales(Decimal('10000'), tpl)['commission'],
            Decimal('0.00'),
        )
        self.assertEqual(
            commission_for_qualifying_sales(Decimal('12500'), tpl)['commission'],
            Decimal('500.00'),
        )
        self.assertEqual(
            commission_for_qualifying_sales(Decimal('25000'), tpl)['commission'],
            Decimal('1000.00'),
        )
        self.assertEqual(
            commission_for_qualifying_sales(Decimal('35000'), tpl)['commission'],
            Decimal('2000.00'),
        )
        self.assertEqual(
            commission_for_qualifying_sales(Decimal('45000'), tpl)['commission'],
            Decimal('3500.00'),
        )
        self.assertEqual(
            commission_for_qualifying_sales(Decimal('50000'), tpl)['commission'],
            Decimal('4000.00'),
        )


class AgentCommissionDayAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.manager_user)
        self.field_role = Role.objects.get(name=ROLE_FIELD_AGENT)
        self.agent = User.objects.create_user(
            username='day_agent', password='x', first_name='Dee'
        )
        UserProfile.objects.create(
            user=self.agent,
            role='cashier',
            custom_role=self.field_role,
            is_active=True,
        )
        category = Category.objects.create(name='Day Cat', is_active=True)
        self.product = Product.objects.create(
            name='Agent Kit',
            sku='AK-1',
            category=category,
            price=Decimal('1000'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )
        self.zip_product = Product.objects.create(
            name='Metal Zip #5',
            sku='ZIP-1',
            category=category,
            price=Decimal('100'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )
        settings = PayrollSettings.load()
        settings.include_sales_commission = True
        settings.sales_commission_template = DEFAULT_COMMISSION_TEMPLATE
        settings.save()

    def _auth_as_agent(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        client = self.client.__class__()
        token = RefreshToken.for_user(self.agent)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def _sale(self, *, total, day, product=None, paid=None):
        product = product or self.product
        paid = total if paid is None else paid
        sale = Sale.objects.create(
            sale_number=f'DAY-{total}-{day.isoformat()}',
            status='completed',
            sale_type='pos',
            entry_source='field',
            subtotal=total,
            total=total,
            amount_paid=paid,
            payment_method='cash',
            cashier=self.agent,
            served_by=self.agent,
            occurred_at=timezone.make_aware(
                datetime(day.year, day.month, day.day, 11, 0, 0)
            ),
        )
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=1,
            unit_price=total,
            subtotal=total,
        )
        return sale

    def test_agent_day_dashboard_and_previous_day(self):
        today = date(2026, 11, 10)
        yesterday = date(2026, 11, 9)
        self._sale(total=Decimal('25000.00'), day=today)
        self._sale(total=Decimal('15000.00'), day=yesterday)
        with patch('django.utils.timezone.localdate', return_value=today):
            with patch(
                'settings.module_features.is_module_feature_enabled',
                return_value=True,
            ):
                payload = agent_day_commission(self.agent.id, today)
                self.assertEqual(payload['commission'], '1000.00')
                self.assertEqual(payload['qualifying_sales'], '25000.00')
                self.assertTrue(payload['transport']['qualified'])

                past = agent_day_commission(self.agent.id, yesterday)
                self.assertEqual(past['date'], '2026-11-09')
                self.assertEqual(past['commission'], '500.00')
                self.assertFalse(past['is_today'])

                client = self._auth_as_agent()
                res = client.get('/api/payroll/me/commission-day/')
                self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
                self.assertEqual(res.data['commission'], '1000.00')

                res_past = client.get(
                    '/api/payroll/me/commission-day/',
                    {'date': '2026-11-09'},
                )
                self.assertEqual(res_past.status_code, status.HTTP_200_OK, res_past.data)
                self.assertEqual(res_past.data['commission'], '500.00')

    def test_excludes_zip_lines_and_unpaid(self):
        day = date(2026, 11, 8)
        self._sale(total=Decimal('20000.00'), day=day)
        self._sale(total=Decimal('10000.00'), day=day, product=self.zip_product)
        self._sale(total=Decimal('30000.00'), day=day, paid=Decimal('1000.00'))
        with patch(
            'settings.module_features.is_module_feature_enabled', return_value=True
        ):
            payload = agent_day_commission(self.agent.id, day)
        # Only the 20k qualifying kit sale counts → 1,000 commission band
        self.assertEqual(payload['qualifying_sales'], '20000.00')
        self.assertEqual(payload['commission'], '1000.00')
        self.assertEqual(payload['excluded_lines'], '10000.00')
