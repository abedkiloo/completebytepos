"""Query-budget checks for FIFO stock layers (avoid N+1 on hot paths)."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from inventory.models import StockLayer
from inventory.services import StockMovementService
from inventory.stock_layers import bulk_ensure_opening_layers, open_layers_prefetch
from products.models import Category, Product
from products.serializers import ProductSerializer
from products.stock_utils import sellable_unit_cost, sellable_unit_price
from reports.stock_valuation import StockValuationReportService
from settings.test_utils import disable_maker_checker


class StockLayersPerfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maker_checker()
        cls.user = User.objects.create_user(username='layer_perf', password='x')
        cat = Category.objects.create(name='Perf Cat', is_active=True)
        cls.products = []
        for i in range(12):
            p = Product.objects.create(
                name=f'Perf SKU {i}',
                sku=f'PERF-{i:03d}',
                category=cat,
                price=Decimal('100.00') + i,
                cost=Decimal('50.00') + i,
                stock_quantity=5 + i,
                track_stock=True,
                is_active=True,
            )
            cls.products.append(p)
        # Materialize opening layers once (as migrate would).
        bulk_ensure_opening_layers()
        inv = StockMovementService()
        # Second layer on first product so valuation has multiple rows.
        inv.purchase_stock(
            product_id=cls.products[0].id,
            variant_id=None,
            quantity=10,
            unit_cost=Decimal('40.00'),
            unit_sell_price=Decimal('90.00'),
            user=cls.user,
        )

    def test_bulk_ensure_is_constant_query_budget(self):
        # Already layered — should not create, and stay within a small budget.
        with CaptureQueriesContext(connection) as ctx:
            created = bulk_ensure_opening_layers()
        self.assertEqual(created, 0)
        # open keys + simple products + variants + shell ids (+ maybe variants lookup)
        self.assertLessEqual(len(ctx), 8)

    def test_valuation_query_count_does_not_grow_with_sku_count(self):
        with CaptureQueriesContext(connection) as ctx:
            report = StockValuationReportService.build()
        self.assertGreaterEqual(report['summary']['item_count'], 12)
        # Must not be O(SKUs) exists()/fetch (~2–3 queries per SKU would be 24+).
        self.assertLessEqual(len(ctx), 20)

    def test_sellable_price_cost_do_not_query_layers_per_product(self):
        with CaptureQueriesContext(connection) as ctx:
            for product in self.products:
                sellable_unit_price(product)
                sellable_unit_cost(product)
        # Catalog fields only — zero layer lookups for N products.
        self.assertEqual(len(ctx), 0)

    def test_product_serializer_uses_prefetched_layers(self):
        product = (
            Product.objects.filter(pk=self.products[0].pk)
            .prefetch_related(open_layers_prefetch())
            .get()
        )
        with CaptureQueriesContext(connection) as ctx:
            data = ProductSerializer(product).data
        self.assertGreaterEqual(len(data.get('stock_layers') or []), 1)
        # Prefetched — serializing layers should not hit StockLayer again.
        layer_queries = [
            q for q in ctx.captured_queries if 'inventory_stocklayer' in q['sql'].lower()
        ]
        self.assertEqual(layer_queries, [])
