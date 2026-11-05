"""Payments trail Excel export — day money-in workbook."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from openpyxl import load_workbook
from rest_framework import status

from products.models import Category, Product
from sales.models import (
    Customer,
    CustomerWalletTransaction,
    Invoice,
    Payment,
    Sale,
    SaleItem,
)
from sales.module_settings import sales_payments_trail_export_enabled
from sales.payments_trail import build_payments_trail_export
from sales.services import CustomerService
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


def _set_feature(module_name: str, feature_key: str, enabled: bool) -> None:
    module, _ = ModuleSettings.objects.get_or_create(
        module_name=module_name,
        defaults={'is_enabled': True},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feat, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key=feature_key,
        defaults={'feature_name': feature_key, 'is_enabled': enabled},
    )
    feat.is_enabled = enabled
    feat.save(update_fields=['is_enabled'])


class PaymentsTrailExportTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _set_feature('sales', 'payments_trail_export', True)
        self.today = timezone.localdate()
        self.customer = Customer.objects.create(
            name='Export Customer',
            phone='0700333444',
            wallet_balance=Decimal('-300.00'),
            is_active=True,
        )
        category = Category.objects.create(name='Export Cat', is_active=True)
        self.product = Product.objects.create(
            name='Export Item',
            sku='EXP-1',
            category=category,
            price=Decimal('200'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        # Cash sale tender
        self.cash_sale = Sale.objects.create(
            sale_number='SALE-EXP-CASH',
            status='completed',
            sale_type='pos',
            customer=self.customer,
            subtotal=Decimal('200.00'),
            total=Decimal('200.00'),
            amount_paid=Decimal('200.00'),
            payment_method='cash',
            cashier=self.manager_user,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=self.cash_sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('200'),
            subtotal=Decimal('200'),
        )
        # Debt sale + M-Pesa settlement
        self.debt_sale = Sale.objects.create(
            sale_number='SALE-EXP-DEBT',
            status='completed',
            sale_type='pos',
            customer=self.customer,
            subtotal=Decimal('300.00'),
            total=Decimal('300.00'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            cashier=self.manager_user,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=self.debt_sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('300'),
            subtotal=Decimal('300'),
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('300.00'),
            balance_after=Decimal('-300.00'),
            sale=self.debt_sale,
            created_by=self.manager_user,
        )
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('150.00'),
            payment_method='mpesa',
            reference='QHXEXPORT01',
            user=self.manager_user,
        )
        # Invoice bank transfer
        inv_sale = Sale.objects.create(
            sale_number='SALE-EXP-INV',
            status='completed',
            customer=self.customer,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            cashier=self.manager_user,
            occurred_at=timezone.now(),
        )
        self.invoice = Invoice.objects.create(
            sale=inv_sale,
            customer=self.customer,
            customer_name=self.customer.name,
            issued_date=self.today,
            due_date=self.today + timedelta(days=7),
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('0'),
            balance=Decimal('100'),
            status='sent',
            created_by=self.manager_user,
        )
        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal('100.00'),
            payment_method='bank_transfer',
            payment_date=self.today,
            reference='BANK-EXP-1',
            recorded_by=self.manager_user,
        )
        self.invoice.amount_paid = Decimal('100.00')
        self.invoice.balance = Decimal('0')
        self.invoice.status = 'paid'
        self.invoice.save(update_fields=['amount_paid', 'balance', 'status'])

    def test_build_export_includes_cash_mpesa_bank(self):
        payload = build_payments_trail_export(
            date_from=self.today.isoformat(),
            date_to=self.today.isoformat(),
            user=self.manager_user,
        )
        methods = {row['payment_method'] for row in payload['results']}
        self.assertIn('cash', methods)
        self.assertIn('mpesa', methods)
        self.assertIn('bank_transfer', methods)
        by_method = {row['payment_method']: row for row in payload['by_method']}
        self.assertGreaterEqual(by_method['cash']['count'], 1)
        self.assertGreaterEqual(by_method['mpesa']['count'], 1)
        self.assertGreaterEqual(by_method['bank_transfer']['count'], 1)

    def test_export_api_xlsx(self):
        response = self.client.get(
            '/api/sales/customers/payments-trail/export/',
            {
                'date_from': self.today.isoformat(),
                'date_to': self.today.isoformat(),
                'format': 'xlsx',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, getattr(response, 'data', None))
        self.assertIn(
            'spreadsheetml',
            response['Content-Type'],
        )
        wb = load_workbook(BytesIO(response.content))
        self.assertIn('Payments', wb.sheetnames)
        self.assertIn('By method', wb.sheetnames)
        payments = wb['Payments']
        # Header row after title block
        headers = [cell.value for cell in next(payments.iter_rows(min_row=6, max_row=6))]
        self.assertIn('Amount', headers)
        self.assertIn('Method', headers)
        data_rows = list(payments.iter_rows(min_row=7, values_only=True))
        self.assertGreaterEqual(len(data_rows), 3)
        method_col = headers.index('Method')
        methods = {row[method_col] for row in data_rows if row and row[method_col]}
        self.assertTrue(methods & {'Cash', 'M-PESA', 'Bank transfer'})

    def test_export_feature_off_forbidden(self):
        _set_feature('sales', 'payments_trail_export', False)
        self.assertFalse(sales_payments_trail_export_enabled())
        response = self.client.get(
            '/api/sales/customers/payments-trail/export/',
            {
                'date_from': self.today.isoformat(),
                'date_to': self.today.isoformat(),
                'format': 'xlsx',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_requires_xlsx_format(self):
        response = self.client.get(
            '/api/sales/customers/payments-trail/export/',
            {
                'date_from': self.today.isoformat(),
                'date_to': self.today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
