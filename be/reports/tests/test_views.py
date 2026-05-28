"""Phase 2 — ReportViewSet API integration tests."""

from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from expenses.models import Expense, ExpenseCategory
from inventory.models import StockMovement
from products.models import Category, Product
from sales.models import Sale, SaleItem
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class ReportsViewsTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Report Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Report Product',
            sku='RPT-PROD-001',
            category=cat,
            price=Decimal('200.00'),
            cost=Decimal('100.00'),
            stock_quantity=10,
            low_stock_threshold=5,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('200.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('200.00'),
            amount_paid=Decimal('200.00'),
            cashier=cls.manager_user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=1,
            unit_price=Decimal('200.00'),
            subtotal=Decimal('200.00'),
        )
        StockMovement.objects.create(
            product=cls.product,
            movement_type='purchase',
            quantity=10,
            unit_cost=Decimal('100.00'),
            total_cost=Decimal('1000.00'),
            user=cls.manager_user,
        )
        exp_cat = ExpenseCategory.objects.create(name='Ops', is_active=True)
        Expense.objects.create(
            category=exp_cat,
            description='Rent',
            amount=Decimal('500.00'),
            expense_date=timezone.now().date(),
            status='approved',
            payment_method='cash',
            created_by=cls.manager_user,
        )

    def test_dashboard_requires_auth(self):
        anon = APIClient()
        response = anon.get('/api/reports/dashboard/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_dashboard_includes_today_and_growth(self):
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('today', response.data)
        self.assertIn('growth', response.data)
        self.assertIn('profit', response.data)
        self.assertGreaterEqual(response.data['today']['sales_count'], 1)

    def test_sales_report_summary(self):
        response = self.client.get('/api/reports/sales/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('by_payment_method', response.data)
        self.assertIn('daily_breakdown', response.data)

    def test_products_report_lists_sold_items(self):
        response = self.client.get('/api/reports/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('products', response.data)
        skus = [p.get('product__sku') for p in response.data['products']]
        self.assertIn('RPT-PROD-001', skus)

    def test_inventory_report_counts_and_movements(self):
        response = self.client.get('/api/reports/inventory/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('low_stock_count', response.data)
        self.assertIn('recent_movements', response.data)
        self.assertGreaterEqual(len(response.data['recent_movements']), 1)

    def test_purchase_report_from_stock_movements(self):
        response = self.client.get('/api/reports/purchase/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('purchases', response.data)
        self.assertGreaterEqual(response.data['summary']['total_purchases'], 1)

    def test_sales_overview_respects_period(self):
        response = self.client.get('/api/reports/sales_overview/', {'period': 'month'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period'], 'month')
        self.assertIn('summary', response.data)
        self.assertIn('trend', response.data)
        self.assertGreaterEqual(response.data['summary']['sales_count'], 1)

    def test_top_products_period_month(self):
        response = self.client.get('/api/reports/top_products/', {'period': 'month'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period'], 'month')
        items = response.data.get('items', [])
        self.assertTrue(any(i['sku'] == 'RPT-PROD-001' for i in items))

    def test_inventory_health_snapshot(self):
        response = self.client.get('/api/reports/inventory_health/', {'period': 'month'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('at_risk', response.data)
        self.assertIn('movements_by_type', response.data)

    def test_cash_and_payments_breakdown(self):
        response = self.client.get('/api/reports/cash_and_payments/', {'period': 'month'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('by_method', response.data)
        self.assertIn('summary', response.data)

    def test_customer_outstanding_empty_ok(self):
        response = self.client.get('/api/reports/customer_outstanding/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('aging', response.data)

    def test_profit_loss_report(self):
        response = self.client.get('/api/reports/profit_loss/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('total_revenue', response.data['summary'])

    def test_annual_report_current_year(self):
        year = timezone.now().year
        response = self.client.get('/api/reports/annual/', {'year': year})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('monthly_data', response.data)
        self.assertEqual(len(response.data['monthly_data']), 12)

    def test_expense_report_approved_only(self):
        response = self.client.get('/api/reports/expense/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('expenses', response.data)
        self.assertGreaterEqual(len(response.data['expenses']), 1)

    def test_tax_report(self):
        response = self.client.get('/api/reports/tax/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)

    def test_supplier_report_from_purchases(self):
        response = self.client.get('/api/reports/supplier/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('suppliers', response.data)


class ReportsPermissionsTestCase(SalesAPITestCase):
    def test_sales_cannot_access_dashboard(self):
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_cannot_access_sales_overview(self):
        response = self.client.get('/api/reports/sales_overview/', {'period': 'today'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
