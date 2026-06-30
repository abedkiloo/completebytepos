from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from inventory.models import StockMovement
from products.models import Product
from sales.backfill_policy import (
    backfill_max_days,
    get_backfill_stock_warnings,
    validate_backfill_occurred_at,
    validate_backfill_reason,
)
from settings.models import StoreSettings
from utils.tests.api_test_base import ManagerAPITestCase


class BackfillPolicyTests(TestCase):
    def test_reason_min_length(self):
        with self.assertRaises(Exception):
            validate_backfill_reason('short')
        self.assertEqual(
            validate_backfill_reason('Forgot during busy Saturday'),
            'Forgot during busy Saturday',
        )

    def test_occurred_at_within_window(self):
        now = timezone.now()
        validate_backfill_occurred_at(now - timedelta(days=5))
        with self.assertRaises(Exception):
            validate_backfill_occurred_at(now - timedelta(days=backfill_max_days() + 1))
        with self.assertRaises(Exception):
            validate_backfill_occurred_at(now + timedelta(days=1))


class BackfillStockWarningTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Pen',
            sku='PEN-01',
            price='50.00',
            cost='20.00',
            stock_quantity=20,
            track_stock=True,
        )

    def test_warns_when_adjustment_after_sale_date(self):
        occurred = timezone.now() - timedelta(days=5)
        StockMovement.objects.create(
            product=self.product,
            movement_type='adjustment',
            quantity=5,
            notes='Stock count',
        )
        warnings = get_backfill_stock_warnings(
            occurred,
            [{'product_id': self.product.id, 'quantity': 1}],
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn('Pen', warnings[0]['message'])


class SaleBackfillAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])
        self.product = Product.objects.create(
            name='Notebook',
            sku='NB-01',
            price='100.00',
            cost='50.00',
            stock_quantity=50,
            track_stock=True,
        )

    def test_backfill_queues_for_approval_when_maker_checker_on(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.backfill_maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])
        occurred = timezone.now() - timedelta(days=3)
        res = self.client.post(
            '/api/sales/backfill/',
            {
                'occurred_at': occurred.isoformat(),
                'backfill_reason': 'Sold offline during power outage',
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'served_by_id': self.manager_user.id,
                'acknowledge_stock_warnings': True,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 202, res.content)
        self.assertIn('pending_change', res.data)

    def test_backfill_creates_sale_with_historical_date(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])
        occurred = timezone.now() - timedelta(days=3)
        res = self.client.post(
            '/api/sales/backfill/',
            {
                'occurred_at': occurred.isoformat(),
                'backfill_reason': 'Sold offline during power outage',
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': '200.00',
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 2,
                        'unit_price': '100.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        data = res.data
        self.assertEqual(data['entry_source'], 'backfill')
        self.assertTrue(data['is_late_entry'])
        self.assertEqual(float(data['total']), 200.0)
        self.assertEqual(data['served_by'], self.manager_user.id)

    def test_preflight_returns_stock_warnings(self):
        occurred = timezone.now() - timedelta(days=4)
        StockMovement.objects.create(
            product=self.product,
            movement_type='adjustment',
            quantity=2,
        )
        res = self.client.post(
            '/api/sales/backfill-preflight/',
            {
                'occurred_at': occurred.isoformat(),
                'items': [{'product_id': self.product.id, 'quantity': 1}],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(len(res.data['warnings']), 1)

    def test_backfill_blocks_without_stock_acknowledgement(self):
        occurred = timezone.now() - timedelta(days=4)
        StockMovement.objects.create(
            product=self.product,
            movement_type='adjustment',
            quantity=2,
        )
        res = self.client.post(
            '/api/sales/backfill/',
            {
                'occurred_at': occurred.isoformat(),
                'backfill_reason': 'Sold offline during power outage',
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('stock_warnings', res.data)

    def test_csv_import_creates_sale(self):
        occurred = timezone.now() - timedelta(days=2)
        csv_body = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id\n'
            f'R1,{occurred.isoformat()},Sold offline during outage,{self.product.sku},1,100.00,'
            'cash,100.00,pos,,,\n'
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        res = self.client.post(
            '/api/sales/backfill-import-csv/',
            {'file': SimpleUploadedFile('sales.csv', csv_body.encode('utf-8'), 'text/csv')},
            format='multipart',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['created'], 1)
        self.assertEqual(res.data['errors'], [])
