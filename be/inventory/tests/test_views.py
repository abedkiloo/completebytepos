"""Phase 2 — StockMovementViewSet API integration tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import StockMovement
from products.models import Category, Color, Product, ProductVariant, Size
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase
from utils.tests.module_setting_helpers import enable_inventory_api_features, enable_products_list_api_fields


class InventoryViewsTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Inv Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Stock Widget',
            sku='INV-VIEW-001',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('60.00'),
            stock_quantity=20,
            low_stock_threshold=5,
            track_stock=True,
            is_active=True,
        )
        cls.low_product = Product.objects.create(
            name='Low Stock Item',
            sku='INV-LOW-001',
            category=cat,
            price=Decimal('50.00'),
            cost=Decimal('30.00'),
            stock_quantity=2,
            low_stock_threshold=5,
            track_stock=True,
            is_active=True,
        )
        cls.out_product = Product.objects.create(
            name='Empty Shelf',
            sku='INV-OUT-001',
            category=cat,
            price=Decimal('25.00'),
            cost=Decimal('10.00'),
            stock_quantity=0,
            low_stock_threshold=3,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        disable_maker_checker()
        enable_products_list_api_fields()
        enable_inventory_api_features()

    def test_list_requires_authentication(self):
        anon = APIClient()
        response = anon.get('/api/inventory/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_list_movements_returns_200(self):
        response = self.client.get('/api/inventory/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_purchase_increases_stock(self):
        response = self.client.post(
            '/api/inventory/purchase/',
            {
                'product_id': self.product.id,
                'quantity': 10,
                'unit_cost': '60.00',
                'notes': 'Test purchase',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 30)
        self.assertEqual(StockMovement.objects.filter(product=self.product, movement_type='purchase').count(), 1)

    def test_adjust_stock_positive_and_negative(self):
        add = self.client.post(
            '/api/inventory/adjust/',
            {'product_id': self.product.id, 'quantity': 5, 'notes': 'Found extra'},
            format='json',
        )
        self.assertEqual(add.status_code, status.HTTP_201_CREATED, add.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 25)

        remove = self.client.post(
            '/api/inventory/adjust/',
            {'product_id': self.product.id, 'quantity': -3, 'notes': 'Damaged'},
            format='json',
        )
        self.assertEqual(remove.status_code, status.HTTP_201_CREATED, remove.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 22)

    def test_adjust_below_zero_returns_400(self):
        response = self.client.post(
            '/api/inventory/adjust/',
            {'product_id': self.product.id, 'quantity': -999, 'notes': 'Too much'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_adjust_variant_stock_via_api(self):
        """Per-variant adjustments update variant qty and record cost on the movement."""
        size = Size.objects.create(name='Medium', code='M', is_active=True)
        color = Color.objects.create(name='Blue', hex_code='#0000FF', is_active=True)
        product = Product.objects.create(
            name='Variant Tee',
            sku='INV-VAR-TEE',
            category=self.product.category,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=0,
            has_variants=True,
            track_stock=True,
            is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=product,
            size=size,
            color=color,
            sku='INV-VAR-TEE-M-BLU',
            price=Decimal('100.00'),
            cost=Decimal('45.00'),
            stock_quantity=6,
            is_active=True,
        )
        product.refresh_from_db()

        response = self.client.post(
            '/api/inventory/adjust/',
            {
                'product_id': product.id,
                'variant_id': variant.id,
                'quantity': 2,
                'notes': 'Cycle count +2',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        variant.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(variant.stock_quantity, 8)
        self.assertEqual(product.stock_quantity, 8)

        movement = StockMovement.objects.filter(
            product=product, variant=variant, movement_type='adjustment'
        ).latest('created_at')
        self.assertEqual(movement.quantity, 2)
        self.assertEqual(movement.unit_cost, Decimal('45.00'))
        self.assertEqual(movement.total_cost, Decimal('90.00'))

    def test_purchase_invalid_product_returns_400(self):
        response = self.client.post(
            '/api/inventory/purchase/',
            {'product_id': 999999, 'quantity': 1, 'unit_cost': '10.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_low_stock_lists_products(self):
        response = self.client.get('/api/inventory/low_stock/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        skus = {p['sku'] for p in response.data}
        self.assertIn('INV-LOW-001', skus)

    def test_out_of_stock_lists_zero_qty(self):
        response = self.client.get('/api/inventory/out_of_stock/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        skus = {p['sku'] for p in response.data}
        self.assertIn('INV-OUT-001', skus)

    def test_needs_reorder_endpoint(self):
        response = self.client.get('/api/inventory/needs_reorder/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(p['sku'] == 'INV-LOW-001' for p in response.data))

    def test_inventory_report_endpoint(self):
        self.client.post(
            '/api/inventory/purchase/',
            {'product_id': self.product.id, 'quantity': 1, 'unit_cost': '60.00'},
            format='json',
        )
        response = self.client.get('/api/inventory/report/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_products', response.data)
        self.assertIn('by_movement_type', response.data)
        self.assertIn('recent_movements', response.data)

    def test_movements_by_type_groups(self):
        self.client.post(
            '/api/inventory/purchase/',
            {'product_id': self.product.id, 'quantity': 2, 'unit_cost': '60.00'},
            format='json',
        )
        response = self.client.get('/api/inventory/movements_by_type/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        types = {row['movement_type'] for row in response.data}
        self.assertIn('purchase', types)

    def test_product_history_requires_product_id(self):
        response = self.client.get('/api/inventory/product_history/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_history_returns_movements(self):
        self.client.post(
            '/api/inventory/adjust/',
            {'product_id': self.product.id, 'quantity': 1},
            format='json',
        )
        response = self.client.get(
            '/api/inventory/product_history/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_bulk_adjust_partial_success(self):
        response = self.client.post(
            '/api/inventory/bulk_adjust/',
            {
                'adjustments': [
                    {'product_id': self.product.id, 'quantity': 2, 'notes': 'bulk 1'},
                    {'product_id': 999999, 'quantity': 1},
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created'], 1)
        self.assertGreaterEqual(len(response.data['errors']), 1)

    def test_filter_movements_by_product(self):
        self.client.post(
            '/api/inventory/purchase/',
            {'product_id': self.product.id, 'quantity': 1, 'unit_cost': '60.00'},
            format='json',
        )
        response = self.client.get('/api/inventory/', {'product': self.product.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertTrue(all(m['product'] == self.product.id for m in results))


class InventoryPermissionsTestCase(SalesAPITestCase):
    """Sales role has no inventory module access — only POS/product view."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Sales Cat')
        cls.product = Product.objects.create(
            name='View Only',
            sku='INV-SALES-001',
            category=cat,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )

    def test_sales_cannot_list_inventory_movements(self):
        response = self.client.get('/api/inventory/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_cannot_purchase_without_create_perm(self):
        response = self.client.post(
            '/api/inventory/purchase/',
            {'product_id': self.product.id, 'quantity': 1, 'unit_cost': '5.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
