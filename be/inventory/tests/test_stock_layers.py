"""FIFO stock layers: cost + selling price per intake."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from inventory.models import StockLayer
from inventory.services import StockMovementService
from inventory.stock_layers import oldest_open_layer
from products.models import Category, Product
from reports.stock_valuation import StockValuationReportService
from sales.models import SaleItem, SaleItemLayerAllocation
from sales.refunds import SaleRefundService
from sales.services import SaleService
from settings.test_utils import disable_maker_checker


class StockLayersFIFOTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        self.user = User.objects.create_user(username='layer_user', password='x')
        cat = Category.objects.create(name='Layers Cat', is_active=True)
        self.product = Product.objects.create(
            name='Rack Stamps',
            sku='RACK-STAMP-1',
            category=cat,
            price=Decimal('500.00'),
            cost=Decimal('400.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        self.inv = StockMovementService()
        self.sales = SaleService()

    def test_purchase_keeps_old_sell_price_until_layer_drained(self):
        # Opening 20 @ cost 400 / sell 500; receive 50 @ 350 / sell 450
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=50,
            unit_cost=Decimal('350.00'),
            unit_sell_price=Decimal('450.00'),
            user=self.user,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 70)
        # Catalog still mirrors oldest open layer (opening / first)
        self.assertEqual(self.product.price, Decimal('500.00'))
        self.assertEqual(self.product.cost, Decimal('400.00'))

        layers = list(
            StockLayer.objects.filter(product=self.product).order_by('received_at', 'id')
        )
        self.assertEqual(len(layers), 2)
        self.assertEqual(layers[0].qty_remaining, 20)
        self.assertEqual(layers[0].unit_cost, Decimal('400.00'))
        self.assertEqual(layers[1].qty_remaining, 50)
        self.assertEqual(layers[1].unit_sell_price, Decimal('450.00'))

        # Sell 20 — drains old layer; next sell price becomes 450
        sale = self.sales.create_sale(
            {
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': Decimal('10000.00'),
            },
            [{'product_id': self.product.id, 'quantity': 20}],
            self.user,
        )
        items = list(sale.items.all())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].unit_price, Decimal('500.00'))
        self.assertEqual(items[0].unit_cost, Decimal('400.00'))
        self.assertEqual(items[0].layer_allocations.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('450.00'))
        self.assertEqual(self.product.cost, Decimal('350.00'))
        oldest = oldest_open_layer(product_id=self.product.id)
        self.assertEqual(oldest.unit_sell_price, Decimal('450.00'))

        sale2 = self.sales.create_sale(
            {
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': Decimal('450.00'),
            },
            [{'product_id': self.product.id, 'quantity': 1}],
            self.user,
        )
        line = sale2.items.get()
        self.assertEqual(line.unit_price, Decimal('450.00'))
        self.assertEqual(line.unit_cost, Decimal('350.00'))

    def test_cross_layer_sale_splits_lines(self):
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=50,
            unit_cost=Decimal('350.00'),
            unit_sell_price=Decimal('450.00'),
            user=self.user,
        )
        sale = self.sales.create_sale(
            {
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': Decimal('12250.00'),
            },
            [{'product_id': self.product.id, 'quantity': 25}],
            self.user,
        )
        items = list(sale.items.order_by('id'))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].quantity, 20)
        self.assertEqual(items[0].unit_price, Decimal('500.00'))
        self.assertEqual(items[0].unit_cost, Decimal('400.00'))
        self.assertEqual(items[1].quantity, 5)
        self.assertEqual(items[1].unit_price, Decimal('450.00'))
        self.assertEqual(items[1].unit_cost, Decimal('350.00'))
        self.assertEqual(sale.subtotal, Decimal('20') * Decimal('500') + Decimal('5') * Decimal('450'))

    def test_valuation_sums_open_layers(self):
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=50,
            unit_cost=Decimal('350.00'),
            unit_sell_price=Decimal('450.00'),
            user=self.user,
        )
        report = StockValuationReportService.build()
        self.assertTrue(report.get('by_layer'))
        rack_rows = [r for r in report['items'] if r['sku'] == 'RACK-STAMP-1']
        self.assertEqual(len(rack_rows), 2)
        value = sum(r['inventory_value'] for r in rack_rows)
        self.assertEqual(value, float(20 * 400 + 50 * 350))

    def test_refund_restores_layer_and_catalog_price(self):
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=50,
            unit_cost=Decimal('350.00'),
            unit_sell_price=Decimal('450.00'),
            user=self.user,
        )
        sale = self.sales.create_sale(
            {
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': Decimal('10000.00'),
            },
            [{'product_id': self.product.id, 'quantity': 20}],
            self.user,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('450.00'))

        SaleRefundService().create_refund(
            sale, reason='Customer return', user=self.user, full=True
        )
        old = StockLayer.objects.filter(
            product=self.product, unit_cost=Decimal('400.00')
        ).first()
        self.assertIsNotNone(old)
        self.assertEqual(old.qty_remaining, 20)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('500.00'))
        self.assertEqual(self.product.cost, Decimal('400.00'))
        alloc = SaleItemLayerAllocation.objects.filter(sale_item__sale=sale).first()
        self.assertEqual(alloc.qty_returned, 20)

    def test_purchase_does_not_blend_wac_when_layers_on(self):
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=50,
            unit_cost=Decimal('350.00'),
            unit_sell_price=Decimal('450.00'),
            user=self.user,
        )
        self.product.refresh_from_db()
        # Must stay at oldest layer cost, not WAC of (20*400+50*350)/70
        self.assertEqual(self.product.cost, Decimal('400.00'))
        self.assertNotEqual(self.product.cost, Decimal('364.29'))
