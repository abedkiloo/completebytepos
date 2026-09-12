"""Tests for daily sales tracking — orders breakdown (paid vs debt) and daily summaries."""

from decimal import Decimal
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status

from sales.models import Customer, CustomerWalletTransaction, Sale
from sales.daily_sales import classify_sale_payment, parse_target_date
from utils.tests.api_test_base import ManagerAPITestCase


class DailySalesUnitTests(ManagerAPITestCase):
    def test_parse_target_date_valid(self):
        target, start, end = parse_target_date('2026-09-12')
        self.assertEqual(str(target), '2026-09-12')
        self.assertEqual(start.hour, 0)
        self.assertEqual(start.minute, 0)
        self.assertEqual(end.hour, 23)
        self.assertEqual(end.minute, 59)

    def test_parse_target_date_invalid_raises(self):
        with self.assertRaises(ValueError):
            parse_target_date('invalid-date')

    def test_classify_sale_payment(self):
        # Full payment
        paid, debt, p_status = classify_sale_payment(Decimal('100.00'), Decimal('100.00'))
        self.assertEqual(paid, Decimal('100.00'))
        self.assertEqual(debt, Decimal('0.00'))
        self.assertEqual(p_status, 'paid')

        # Overpayment or change
        paid, debt, p_status = classify_sale_payment(Decimal('100.00'), Decimal('150.00'))
        self.assertEqual(paid, Decimal('100.00'))
        self.assertEqual(debt, Decimal('0.00'))
        self.assertEqual(p_status, 'paid')

        # Full debt (pay later)
        paid, debt, p_status = classify_sale_payment(Decimal('200.00'), Decimal('0.00'))
        self.assertEqual(paid, Decimal('0.00'))
        self.assertEqual(debt, Decimal('200.00'))
        self.assertEqual(p_status, 'debt')

        # Partial payment
        paid, debt, p_status = classify_sale_payment(Decimal('300.00'), Decimal('100.00'))
        self.assertEqual(paid, Decimal('100.00'))
        self.assertEqual(debt, Decimal('200.00'))
        self.assertEqual(p_status, 'partial')


class DailySalesAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.target_date_str = '2026-09-12'
        tz = timezone.get_current_timezone()
        dt_target = datetime.strptime(self.target_date_str, '%Y-%m-%d')
        self.target_occurred_at = timezone.make_aware(
            dt_target.replace(hour=10, minute=30), tz
        )
        self.other_occurred_at = timezone.make_aware(
            (dt_target - timedelta(days=2)).replace(hour=14, minute=0), tz
        )

        self.customer = Customer.objects.create(
            name='Daily Debtor',
            phone='0711000111',
            wallet_balance=Decimal('-2500.00'),
            is_active=True,
        )

        # Sale 1: Fully Paid on target date
        self.sale_paid = Sale.objects.create(
            sale_number='SALE-PAID-01',
            status='completed',
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            amount_paid=Decimal('1000.00'),
            payment_method='cash',
            occurred_at=self.target_occurred_at,
            cashier=self.manager_user,
        )

        # Sale 2: Partial payment on target date (debt incurred)
        self.sale_partial = Sale.objects.create(
            sale_number='SALE-PARTIAL-02',
            status='completed',
            subtotal=Decimal('2500.00'),
            total=Decimal('2500.00'),
            amount_paid=Decimal('500.00'),
            payment_method='mpesa',
            customer=self.customer,
            occurred_at=self.target_occurred_at + timedelta(minutes=15),
            cashier=self.manager_user,
        )

        # Sale 3: Full debt (pay later) on target date
        self.sale_full_debt = Sale.objects.create(
            sale_number='SALE-DEBT-03',
            status='completed',
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
            amount_paid=Decimal('0.00'),
            payment_method='other',
            customer=self.customer,
            occurred_at=self.target_occurred_at + timedelta(minutes=45),
            cashier=self.manager_user,
        )

        # Sale 4: Different date (should NOT be included in target date report)
        self.sale_other_day = Sale.objects.create(
            sale_number='SALE-OTHER-04',
            status='completed',
            subtotal=Decimal('800.00'),
            total=Decimal('800.00'),
            amount_paid=Decimal('800.00'),
            payment_method='cash',
            occurred_at=self.other_occurred_at,
            cashier=self.manager_user,
        )

        # Settlement of prior customer debt collected on target date
        self.settlement_txn = CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('400.00'),
            balance_after=Decimal('-2100.00'),
            reference='SETTLE-TARGET',
        )
        CustomerWalletTransaction.objects.filter(id=self.settlement_txn.id).update(
            created_at=self.target_occurred_at
        )

    def test_daily_sales_report_aggregates(self):
        url = f'/api/sales/daily/?date={self.target_date_str}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data['date'], self.target_date_str)

        summary = data['summary']
        self.assertEqual(summary['orders_count'], 3)
        self.assertEqual(Decimal(summary['total_sales']), Decimal('5000.00'))
        self.assertEqual(Decimal(summary['total_paid']), Decimal('1500.00'))
        self.assertEqual(summary['paid_orders_count'], 1)
        self.assertEqual(Decimal(summary['total_debt_incurred']), Decimal('3500.00'))
        self.assertEqual(summary['debt_orders_count'], 2)
        self.assertEqual(summary['partial_orders_count'], 1)
        self.assertEqual(Decimal(summary['total_debt_collected']), Decimal('400.00'))
        self.assertEqual(summary['debt_settlement_count'], 1)
        # Total collected = 1500 (upfront) + 400 (debt collected) = 1900
        self.assertEqual(Decimal(summary['total_collected']), Decimal('1900.00'))

        self.assertEqual(len(data['orders']), 3)

    def test_filter_by_payment_status_paid(self):
        url = f'/api/sales/daily/?date={self.target_date_str}&payment_status=paid'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        orders = response.data['orders']
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['sale_number'], 'SALE-PAID-01')
        self.assertEqual(orders[0]['payment_status'], 'paid')

    def test_filter_by_payment_status_debt(self):
        url = f'/api/sales/daily/?date={self.target_date_str}&payment_status=debt'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        orders = response.data['orders']
        self.assertEqual(len(orders), 2)
        numbers = {o['sale_number'] for o in orders}
        self.assertEqual(numbers, {'SALE-PARTIAL-02', 'SALE-DEBT-03'})

    def test_filter_by_payment_status_partial(self):
        url = f'/api/sales/daily/?date={self.target_date_str}&payment_status=partial'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        orders = response.data['orders']
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['sale_number'], 'SALE-PARTIAL-02')
        self.assertEqual(orders[0]['payment_status'], 'partial')

    def test_filter_by_search(self):
        url = f'/api/sales/daily/?date={self.target_date_str}&search=Daily Debtor'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        orders = response.data['orders']
        self.assertEqual(len(orders), 2)

    def test_filter_by_payment_method(self):
        url = f'/api/sales/daily/?date={self.target_date_str}&payment_method=mpesa'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        orders = response.data['orders']
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['sale_number'], 'SALE-PARTIAL-02')

    def test_invalid_date_returns_400(self):
        url = '/api/sales/daily/?date=invalid-string'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
