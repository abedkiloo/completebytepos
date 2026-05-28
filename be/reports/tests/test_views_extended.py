"""Extended reports API tests — income, customers, invoices, date filters."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from expenses.models import Expense, ExpenseCategory
from income.models import Income, IncomeCategory
from inventory.models import StockMovement
from products.models import Category, Product
from sales.models import Customer, Invoice, Payment, Sale, SaleItem
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


class ReportsExtendedTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Ext Report Cat')
        cls.product = Product.objects.create(
            name='Ext Report Product',
            sku='RPT-EXT-001',
            category=cat,
            price=Decimal('150.00'),
            cost=Decimal('80.00'),
            stock_quantity=5,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Report Customer Ltd',
            phone='0700000001',
            created_by=cls.manager_user,
        )
        cls.sale_tax = Sale.objects.create(
            status='completed',
            payment_method='mpesa',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('16.00'),
            discount_amount=Decimal('0'),
            total=Decimal('116.00'),
            amount_paid=Decimal('116.00'),
            cashier=cls.manager_user,
        )
        SaleItem.objects.create(
            sale=cls.sale_tax,
            product=cls.product,
            quantity=1,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('100.00'),
        )
        cls.invoice = Invoice.objects.create(
            customer=cls.customer,
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('1000.00'),
            amount_paid=Decimal('200.00'),
            due_date=timezone.now().date() - timedelta(days=45),
            issued_date=timezone.now().date() - timedelta(days=50),
            created_by=cls.manager_user,
        )
        inc_cat = IncomeCategory.objects.create(name='Services', is_active=True)
        cls.income = Income.objects.create(
            category=inc_cat,
            description='Consulting fee',
            amount=Decimal('2500.00'),
            income_date=timezone.now().date(),
            status='approved',
            payment_method='bank',
            created_by=cls.manager_user,
        )
        exp_cat = ExpenseCategory.objects.create(name='Utilities', is_active=True)
        Expense.objects.create(
            category=exp_cat,
            description='Power bill',
            amount=Decimal('300.00'),
            expense_date=timezone.now().date(),
            status='approved',
            payment_method='mpesa',
            created_by=cls.manager_user,
        )
        StockMovement.objects.create(
            product=cls.product,
            movement_type='purchase',
            quantity=5,
            unit_cost=Decimal('80.00'),
            total_cost=Decimal('400.00'),
            reference='SUP-ACME',
            user=cls.manager_user,
        )
        Payment.objects.create(
            invoice=cls.invoice,
            amount=Decimal('100.00'),
            payment_method='cash',
            payment_date=timezone.now().date(),
            recorded_by=cls.manager_user,
        )

    def test_income_report_lists_records(self):
        response = self.client.get('/api/reports/income/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('income', response.data)
        self.assertGreaterEqual(len(response.data['income']), 1)
        self.assertGreater(float(response.data['summary']['total_income'] or 0), 0)

    def test_customer_report_from_invoices(self):
        response = self.client.get('/api/reports/customer/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('customers', response.data)
        names = [c['name'] for c in response.data['customers']]
        self.assertIn('Report Customer Ltd', names)
        self.assertGreaterEqual(response.data['summary']['total_customers'], 1)

    def test_invoice_report_lists_open_invoices(self):
        response = self.client.get('/api/reports/invoice/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('invoices', response.data)
        numbers = [i['invoice_number'] for i in response.data['invoices']]
        self.assertIn(self.invoice.invoice_number, numbers)
        self.assertGreater(float(response.data['summary']['outstanding_amount'] or 0), 0)

    def test_customer_outstanding_with_aging_buckets(self):
        response = self.client.get('/api/reports/customer_outstanding/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['summary']['total_outstanding'], 0)
        self.assertGreaterEqual(response.data['summary']['invoice_count'], 1)
        buckets = {row['bucket']: row['amount'] for row in response.data['aging']}
        self.assertTrue(any(amount > 0 for amount in buckets.values()))
        self.assertGreater(response.data['summary']['overdue_count'], 0)

    def test_tax_report_includes_taxable_sales(self):
        response = self.client.get('/api/reports/tax/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(float(response.data['summary']['total_tax'] or 0), 0)
        self.assertGreaterEqual(len(response.data['tax_breakdown']), 1)

    def test_sales_report_with_date_range(self):
        start = (timezone.now() - timedelta(days=1)).isoformat()
        response = self.client.get(
            '/api/reports/sales/',
            {'date_from': start},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['summary']['total_sales'], 1)

    def test_products_report_with_date_range(self):
        today = timezone.now().isoformat()
        response = self.client.get(
            '/api/reports/products/',
            {'date_from': today},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('products', response.data)

    def test_purchase_report_with_reference_supplier_grouping(self):
        response = self.client.get('/api/reports/purchase/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['purchases']), 1)

    def test_supplier_report_groups_by_reference(self):
        response = self.client.get('/api/reports/supplier/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        suppliers = response.data['suppliers']
        self.assertTrue(any(s['name'] == 'SUP-ACME' for s in suppliers))

    def test_expense_report_with_date_filter(self):
        today = timezone.now().date().isoformat()
        response = self.client.get('/api/reports/expense/', {'date_from': today})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['expenses']), 1)

    def test_profit_loss_with_date_filter(self):
        today = timezone.now().date().isoformat()
        response = self.client.get(
            '/api/reports/profit_loss/',
            {'date_from': today, 'date_to': today},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('monthly_breakdown', response.data)

    def test_sales_overview_periods(self):
        for period in ('today', 'week', 'year'):
            response = self.client.get('/api/reports/sales_overview/', {'period': period})
            self.assertEqual(response.status_code, status.HTTP_200_OK, period)
            self.assertEqual(response.data['period'], period)

    def test_top_products_period_today(self):
        response = self.client.get('/api/reports/top_products/', {'period': 'today'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('items', response.data)

    def test_inventory_health_period_week(self):
        response = self.client.get('/api/reports/inventory_health/', {'period': 'week'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['summary']['low_stock_count'], 1)

    def test_cash_and_payments_includes_invoice_payments(self):
        response = self.client.get('/api/reports/cash_and_payments/', {'period': 'month'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        methods = {row['method'] for row in response.data['by_method']}
        self.assertTrue('cash' in methods or 'mpesa' in methods)

    def test_dashboard_reflects_low_stock(self):
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['low_stock_count'], 1)

    def test_annual_report_growth_rate(self):
        year = timezone.now().year
        response = self.client.get('/api/reports/annual/', {'year': year})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('growth_rate', response.data['summary'])


class ReportsSuperAdminTestCase(SuperAdminAPITestCase):
    def test_super_admin_can_access_all_report_endpoints(self):
        endpoints = [
            '/api/reports/dashboard/',
            '/api/reports/income/',
            '/api/reports/customer/',
            '/api/reports/sales_overview/?period=month',
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, url)
