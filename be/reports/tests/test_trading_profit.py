"""Trading profit report — week/month/year, reports.profit access."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from expenses.models import Expense, ExpenseCategory
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund, SaleRefundItem
from utils.tests.api_test_base import ManagerAPITestCase


class TradingProfitAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ensure_permissions()
        sync_default_roles()
        cls.cat = Category.objects.create(name='TP Cat', is_active=True)
        cls.product = Product.objects.create(
            name='TP Item',
            sku='TP-1',
            category=cls.cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )
        cls.expense_cat = ExpenseCategory.objects.create(name='Rent', is_active=True)

    def _admin_client(self):
        admin = User.objects.create_user('tp_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def _seed_period_data(self):
        sale = Sale.objects.create(
            sale_number='S-TP-1',
            status='completed',
            subtotal=Decimal('200'),
            total=Decimal('200'),
            tax_amount=Decimal('0'),
            payment_method='cash',
            amount_paid=Decimal('200'),
            cashier=self.manager_user,
            occurred_at=timezone.now(),
        )
        line = SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=2,
            unit_price=Decimal('100'),
            unit_cost=Decimal('40'),
            subtotal=Decimal('200'),
        )
        refund = SaleRefund.objects.create(
            sale=sale,
            refund_type='partial',
            amount=Decimal('50'),
            reason='Damaged',
            refunded_by=self.manager_user,
        )
        SaleRefundItem.objects.create(
            refund=refund,
            sale_item=line,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            subtotal=Decimal('50'),
        )
        Expense.objects.create(
            category=self.expense_cat,
            amount=Decimal('30'),
            expense_date=timezone.localdate(),
            status='approved',
            description='Shop rent share',
            created_by=self.manager_user,
        )
        return sale

    def test_manager_denied_without_reports_profit(self):
        self._seed_period_data()
        resp = self.client.get('/api/reports/trading_profit/', {'period': 'month'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_sees_trading_profit_for_month(self):
        self._seed_period_data()
        admin = self._admin_client()
        resp = admin.get('/api/reports/trading_profit/', {'period': 'month'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        summary = resp.data['summary']
        self.assertEqual(summary['basis'], 'trading')
        # Gross 200 − refund 50 = 150 net sales
        self.assertEqual(summary['gross_sales'], 200.0)
        self.assertEqual(summary['refunds'], 50.0)
        self.assertEqual(summary['net_sales'], 150.0)
        # COGS sold 2×40=80; refund restores 1×40=40 → COGS 40
        self.assertEqual(summary['cogs_sold'], 80.0)
        self.assertEqual(summary['cogs_refunded'], 40.0)
        self.assertEqual(summary['cogs'], 40.0)
        # Gross profit 150 − 40 = 110; − expenses 30 = 80
        self.assertEqual(summary['gross_profit'], 110.0)
        self.assertEqual(summary['expenses'], 30.0)
        self.assertEqual(summary['net_profit'], 80.0)
        self.assertEqual(resp.data['period'], 'month')

    def test_week_and_year_periods_ok(self):
        self._seed_period_data()
        admin = self._admin_client()
        for period in ('week', 'year'):
            resp = admin.get('/api/reports/trading_profit/', {'period': period})
            self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
            self.assertEqual(resp.data['period'], period)
            self.assertIn('net_profit', resp.data['summary'])

    def test_granting_profit_permission_allows_manager(self):
        from accounts.models import Permission

        ensure_permissions()
        Role.objects.get(name=ROLE_MANAGER).permissions.add(
            Permission.objects.get(module='reports', action='profit')
        )
        self._seed_period_data()
        resp = self.client.get('/api/reports/trading_profit/', {'period': 'week'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['summary']['basis'], 'trading')

    def test_custom_past_date_range(self):
        """Backdated From/To includes sales in that window and excludes today."""
        from datetime import datetime, time, timedelta

        past_day = timezone.localdate() - timedelta(days=45)
        past_dt = timezone.make_aware(datetime.combine(past_day, time.min))
        Sale.objects.create(
            sale_number='S-TP-PAST',
            status='completed',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            tax_amount=Decimal('0'),
            payment_method='cash',
            amount_paid=Decimal('100'),
            cashier=self.manager_user,
            occurred_at=past_dt,
        )
        SaleItem.objects.create(
            sale=Sale.objects.get(sale_number='S-TP-PAST'),
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            unit_cost=Decimal('40'),
            subtotal=Decimal('100'),
        )
        # Today sale must not appear in the past window
        self._seed_period_data()

        admin = self._admin_client()
        day = past_day.isoformat()
        resp = admin.get(
            '/api/reports/trading_profit/',
            {'date_from': day, 'date_to': day},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        summary = resp.data['summary']
        self.assertEqual(summary['gross_sales'], 100.0)
        self.assertEqual(summary['cogs'], 40.0)
        self.assertEqual(summary['net_profit'], 60.0)
        self.assertEqual(summary['sale_count'], 1)
        self.assertTrue(str(resp.data['date_from']).startswith(day))
        self.assertTrue(str(resp.data['date_to']).startswith(day))

    def test_cogs_breakdown_shows_sale_lines(self):
        self._seed_period_data()
        admin = self._admin_client()
        resp = admin.get('/api/reports/trading_profit/cogs/', {'period': 'month'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['cogs_sold'], 80.0)
        self.assertEqual(resp.data['cogs_refunded'], 40.0)
        self.assertEqual(resp.data['cogs'], 40.0)
        self.assertGreaterEqual(len(resp.data['sales']), 1)
        sale = resp.data['sales'][0]
        self.assertEqual(sale['sale_number'], 'S-TP-1')
        self.assertTrue(sale['lines'])
        self.assertEqual(sale['lines'][0]['line_cogs'], 80.0)

    def test_excluded_category_expense_not_in_trading_profit(self):
        self._seed_period_data()
        drawings = ExpenseCategory.objects.create(
            name='Owner drawings',
            is_active=True,
            include_in_trading_profit=False,
        )
        Expense.objects.create(
            category=drawings,
            amount=Decimal('100'),
            expense_date=timezone.localdate(),
            status='approved',
            description='Owner drawing — not trading',
            created_by=self.manager_user,
        )
        admin = self._admin_client()
        resp = admin.get('/api/reports/trading_profit/', {'period': 'month'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        summary = resp.data['summary']
        # Seed expense 30 still counts; excluded category 100 does not
        self.assertEqual(summary['expenses'], 30.0)
        self.assertEqual(summary['expenses_excluded'], 100.0)
        self.assertEqual(summary['net_profit'], 80.0)
