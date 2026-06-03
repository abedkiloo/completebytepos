"""Additional inventory view edge-case tests."""

from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from inventory.models import StockMovement
from products.models import Category, Product
from settings.test_utils import enable_multi_branch_support
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase
from utils.tests.module_setting_helpers import enable_inventory_api_features


class InventoryViewsExtendedTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Ext Cat')
        cls.product = Product.objects.create(
            name='Extended Item',
            sku='INV-EXT-001',
            category=cat,
            price=Decimal('120.00'),
            cost=Decimal('70.00'),
            stock_quantity=8,
            track_stock=True,
            is_active=True,
        )
        cls.no_track = Product.objects.create(
            name='Service Item',
            sku='INV-NOTRACK-001',
            category=cat,
            price=Decimal('500.00'),
            cost=Decimal('0.00'),
            stock_quantity=0,
            track_stock=False,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        enable_inventory_api_features()

    def test_retrieve_single_movement(self):
        create = self.client.post(
            '/api/inventory/purchase/',
            {'product_id': self.product.id, 'quantity': 2, 'unit_cost': '70.00'},
            format='json',
        )
        movement_id = create.data['id']
        response = self.client.get(f'/api/inventory/{movement_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['movement_type'], 'purchase')

    def test_movements_by_type_with_date_filters(self):
        StockMovement.objects.create(
            product=self.product,
            movement_type='adjustment',
            quantity=1,
            user=self.manager_user,
        )
        today = timezone.now().date().isoformat()
        response = self.client.get(
            '/api/inventory/movements_by_type/',
            {'date_from': today, 'date_to': today},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_report_scoped_to_product_id(self):
        response = self.client.get(
            '/api/inventory/report/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['tracked_products'], 1)

    def test_bulk_adjust_skips_non_tracked_product(self):
        response = self.client.post(
            '/api/inventory/bulk_adjust/',
            {
                'adjustments': [
                    {'product_id': self.no_track.id, 'quantity': 5},
                ],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created'], 0)
        self.assertTrue(any('does not track stock' in e for e in response.data['errors']))

    def test_purchase_missing_quantity_validation(self):
        response = self.client.post(
            '/api/inventory/purchase/',
            {'product_id': self.product.id, 'unit_cost': '70.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_adjust_missing_product_id_validation(self):
        response = self.client.post(
            '/api/inventory/adjust/',
            {'quantity': 1},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class InventoryBranchQuerysetTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        enable_multi_branch_support()
        cls.tenant, cls.branch_a, cls.branch_b = cls.create_tenant_with_branches(
            cls.manager_user, code='QRY'
        )
        cat = Category.objects.create(name='Query Cat')
        cls.product = Product.objects.create(
            name='Query Product',
            sku='INV-QRY-001',
            category=cat,
            price=Decimal('30.00'),
            cost=Decimal('15.00'),
            stock_quantity=12,
            track_stock=True,
            is_active=True,
        )

    def test_show_all_returns_movements_across_branches(self):
        self.set_session_branch(self.tenant, self.branch_a)
        self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 2,
                'to_branch_id': self.branch_b.id,
            },
            format='json',
        )
        response = self.client.get('/api/inventory/', {'show_all': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertGreaterEqual(len(results), 2)


class InventorySuperAdminAccessTestCase(SuperAdminAPITestCase):
    def test_super_admin_can_purchase(self):
        cat = Category.objects.create(name='SA Cat')
        product = Product.objects.create(
            name='SA Product',
            sku='INV-SA-001',
            category=cat,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=1,
            track_stock=True,
            is_active=True,
        )
        response = self.client.post(
            '/api/inventory/purchase/',
            {'product_id': product.id, 'quantity': 3, 'unit_cost': '5.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
