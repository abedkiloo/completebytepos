"""Close remaining trading_profit.py coverage gaps to 100%."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from products.models import Category, Product
from reports.export import UnsupportedExportFormat
from reports.trading_profit import (
    _cogs_sale_limit_for_request,
    _iso_dt,
    compute_cogs_breakdown,
    compute_metric_breakdown,
)
from sales.models import Customer, CustomerWalletTransaction, Sale, SaleItem


class TradingProfitHelperCoverageTests(SimpleTestCase):
    def test_iso_dt_none_and_non_datetime(self):
        self.assertIsNone(_iso_dt(None))
        self.assertEqual(_iso_dt('already-a-string'), 'already-a-string')
        stamp = datetime(2026, 11, 4, 9, 0, 0)
        self.assertTrue(_iso_dt(stamp).startswith('2026-11-04'))

    def test_cogs_sale_limit_treats_bad_format_as_ui_cap(self):
        request = Mock()
        request.query_params = {'format': 'pptx'}
        request.GET = request.query_params
        with patch(
            'reports.export.normalize_export_format',
            side_effect=UnsupportedExportFormat('pptx'),
        ):
            limit = _cogs_sale_limit_for_request(request, default=25)
        self.assertEqual(limit, 25)


class TradingProfitBranchCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('tp_cov', password='x')
        cat = Category.objects.create(name='TP Cov', is_active=True)
        cls.product = Product.objects.create(
            name='TP Cov Item',
            sku='TP-COV-1',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='', phone='0700111222')

    def test_cogs_uses_unit_price_times_qty_when_subtotal_missing(self):
        sale = Sale.objects.create(
            sale_number='S-TP-SUBTOTAL-NONE',
            status='completed',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('100'),
            cashier=self.user,
            occurred_at=timezone.now(),
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=2,
            unit_price=Decimal('50'),
            unit_cost=Decimal('20'),
            subtotal=Decimal('100'),
        )
        # SaleItem.save() recomputes subtotal — force NULL to hit the price×qty path.
        SaleItem.objects.filter(pk=item.pk).update(subtotal=None)
        breakdown = compute_cogs_breakdown(start=None, end=None)
        row = next(s for s in breakdown['sales'] if s['sale_number'] == 'S-TP-SUBTOTAL-NONE')
        line = row['lines'][0]
        self.assertEqual(line['line_sale'], 100.0)

    def test_debt_collections_breakdown_includes_sale_and_notes(self):
        sale = Sale.objects.create(
            sale_number='S-TP-DEBT-REF',
            status='completed',
            subtotal=Decimal('80'),
            total=Decimal('80'),
            amount_paid=Decimal('0'),
            cashier=self.user,
            customer=self.customer,
            occurred_at=timezone.now(),
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='credit',
            source_type='debt_settlement',
            amount=Decimal('25'),
            balance_after=Decimal('-55'),
            sale=sale,
            notes='Till collection note for coverage',
            created_by=self.user,
        )
        payload = compute_metric_breakdown(
            metric='debt_collections',
            start=None,
            end=None,
        )
        self.assertTrue(payload['rows'])
        row = payload['rows'][0]
        self.assertEqual(row['label'], 'Customer')
        self.assertIn('S-TP-DEBT-REF', row['sublabel'])
        self.assertIn('Till collection note', row['sublabel'])
