"""Unit tests for reports service layer."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from expenses.models import Expense, ExpenseCategory
from products.models import Category, Product
from reports.services import ReportDashboardService, resolve_period
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from sales.models import Sale


class ReportServicesTestCase(TestCase):
    def test_resolve_period_today(self):
        factory = APIRequestFactory()
        wsgi = factory.get('/api/reports/dashboard/', {'period': 'today'})
        start, end, label = resolve_period(Request(wsgi))
        self.assertEqual(label, 'today')
        self.assertIsNotNone(start)

    def test_dashboard_service_returns_expected_keys(self):
        user = User.objects.create_user(username='dash_svc', password='x')
        cat = Category.objects.create(name='Dash Cat')
        product = Product.objects.create(
            name='Dash Product',
            sku='DASH-SVC-1',
            category=cat,
            price=Decimal('50'),
            cost=Decimal('30'),
            stock_quantity=5,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True,
        )
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('50'),
            cashier=user,
        )
        exp_cat = ExpenseCategory.objects.create(name='Ops')
        Expense.objects.create(
            category=exp_cat,
            description='Test',
            amount=Decimal('10'),
            expense_date=timezone.now().date(),
            status='approved',
            created_by=user,
        )
        data = ReportDashboardService.get_dashboard_summary()
        self.assertIn('today', data)
        self.assertIn('week', data)
        self.assertEqual(len(data['week']['days']), 7)
        self.assertGreaterEqual(data['week']['sales_count'], 1)
        self.assertIn('growth', data)
        self.assertGreaterEqual(data['low_stock_count'], 1)

    def test_week_sales_summary_groups_last_seven_days(self):
        from datetime import timedelta

        user = User.objects.create_user(username='week_svc', password='x')
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('20'),
            total=Decimal('20'),
            amount_paid=Decimal('20'),
            cashier=user,
            occurred_at=timezone.now() - timedelta(days=2),
        )
        Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('99'),
            total=Decimal('99'),
            amount_paid=Decimal('99'),
            cashier=user,
            occurred_at=timezone.now() - timedelta(days=10),
        )
        data = ReportDashboardService.get_dashboard_summary()
        self.assertEqual(len(data['week']['days']), 7)
        self.assertEqual(data['week']['sales_count'], 1)
        self.assertEqual(data['week']['total'], 20.0)
        self.assertAlmostEqual(sum(day['total'] for day in data['week']['days']), 20.0)

    def test_dashboard_growth_uses_last_month_baselines(self):
        from datetime import timedelta

        from inventory.models import StockMovement

        user = User.objects.create_user(username='dash_growth', password='x')
        cat = Category.objects.create(name='Growth Cat')
        product = Product.objects.create(
            name='Growth Product',
            sku='GROW-1',
            category=cat,
            price=Decimal('50'),
            cost=Decimal('20'),
            stock_quantity=20,
            low_stock_threshold=2,
            track_stock=True,
            is_active=True,
        )
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=1, minute=0, second=0, microsecond=0)
        last_month = start_of_month - timedelta(days=2)

        this_sale = Sale.objects.create(
            status='completed',
            payment_method='mpesa',
            subtotal=Decimal('80'),
            total=Decimal('80'),
            amount_paid=Decimal('80'),
            cashier=user,
        )
        last_sale = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('40'),
            total=Decimal('40'),
            amount_paid=Decimal('40'),
            cashier=user,
        )
        Sale.objects.filter(pk=last_sale.pk).update(created_at=last_month)

        this_return = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('10'),
            discount_amount=Decimal('20'),
            total=Decimal('0'),
            amount_paid=Decimal('0'),
            cashier=user,
        )
        last_return = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('8'),
            discount_amount=Decimal('16'),
            total=Decimal('0'),
            amount_paid=Decimal('0'),
            cashier=user,
        )
        Sale.objects.filter(pk=this_return.pk).update(total=Decimal('-5'))
        Sale.objects.filter(pk=last_return.pk).update(
            created_at=last_month,
            total=Decimal('-4'),
        )

        this_buy = StockMovement.objects.create(
            product=product,
            movement_type='purchase',
            quantity=4,
            unit_cost=Decimal('10'),
            total_cost=Decimal('40'),
            user=user,
        )
        last_buy = StockMovement.objects.create(
            product=product,
            movement_type='purchase',
            quantity=2,
            unit_cost=Decimal('10'),
            total_cost=Decimal('20'),
            user=user,
        )
        StockMovement.objects.filter(pk=last_buy.pk).update(created_at=last_month)
        StockMovement.objects.create(
            product=product,
            movement_type='return',
            quantity=1,
            unit_cost=Decimal('10'),
            total_cost=Decimal('10'),
            user=user,
        )

        exp_cat = ExpenseCategory.objects.create(name='Growth Ops')
        Expense.objects.create(
            category=exp_cat,
            description='This month',
            amount=Decimal('30'),
            expense_date=now.date(),
            status='approved',
            created_by=user,
        )
        Expense.objects.create(
            category=exp_cat,
            description='Last month',
            amount=Decimal('10'),
            expense_date=last_month.date(),
            status='approved',
            created_by=user,
        )

        data = ReportDashboardService.get_dashboard_summary()
        growth = data['growth']
        self.assertNotEqual(growth['sales'], 0)
        self.assertNotEqual(growth['returns'], 0)
        self.assertNotEqual(growth['purchase'], 0)
        self.assertNotEqual(growth['expenses'], 0)
        self.assertNotEqual(growth['profit'], 0)
        self.assertNotEqual(growth['payment_returns'], 0)
        self.assertGreaterEqual(this_sale.total, 0)
        self.assertGreaterEqual(this_return.total, Decimal('-5'))
        self.assertEqual(this_buy.movement_type, 'purchase')
