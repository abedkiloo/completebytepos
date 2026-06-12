"""Phase 3 — inventory module settings gates."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from products.models import Category, Product
from settings.models import ModuleSetting
from settings.test_utils import disable_maker_checker
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


def _seed_inventory_settings():
    cache.clear()
    for key, default in (
        ('show_stock_movements', True),
        ('enable_stock_adjustments', True),
        ('enable_stock_purchases', True),
        ('enable_stock_transfers', True),
        ('show_low_stock_alerts', True),
        ('show_out_of_stock_alerts', True),
        ('enable_inventory_report', True),
        ('show_movement_cost', True),
        ('allow_movement_undo', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='inventory',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class InventoryModuleSettingsAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Inv Flag Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Inv Flag Product',
            sku='INV-FLG-001',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('60.00'),
            stock_quantity=20,
            low_stock_threshold=5,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        disable_maker_checker()
        _seed_inventory_settings()

    def test_list_movements_forbidden_when_disabled(self):
        SettingsService.set('inventory', 'show_stock_movements', False)
        response = self.client.get('/api/inventory/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_purchase_forbidden_when_disabled(self):
        SettingsService.set('inventory', 'enable_stock_purchases', False)
        response = self.client.post(
            '/api/inventory/purchase/',
            {'product_id': self.product.id, 'quantity': 1},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_adjust_forbidden_when_disabled(self):
        SettingsService.set('inventory', 'enable_stock_adjustments', False)
        response = self.client.post(
            '/api/inventory/adjust/',
            {'product_id': self.product.id, 'quantity': 1},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_low_stock_forbidden_when_alerts_disabled(self):
        SettingsService.set('inventory', 'show_low_stock_alerts', False)
        response = self.client.get('/api/inventory/low_stock/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_report_forbidden_when_disabled(self):
        SettingsService.set('inventory', 'enable_inventory_report', False)
        response = self.client.get('/api/inventory/report/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_movement_list_omits_cost_when_hidden(self):
        SettingsService.set('inventory', 'show_movement_cost', False)
        self.client.post(
            '/api/inventory/purchase/',
            {
                'product_id': self.product.id,
                'quantity': 1,
                'unit_cost': '60.00',
            },
            format='json',
        )
        response = self.client.get('/api/inventory/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', response.data)
        self.assertTrue(len(rows) > 0)
        self.assertNotIn('unit_cost', rows[0])
        self.assertNotIn('total_cost', rows[0])
