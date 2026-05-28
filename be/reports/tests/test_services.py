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
        self.assertIn('growth', data)
        self.assertGreaterEqual(data['low_stock_count'], 1)
