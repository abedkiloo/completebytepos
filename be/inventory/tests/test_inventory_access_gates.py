"""Inventory gates: ModuleSetting AND catalog ModuleFeature."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from products.models import Category, Product
from settings.models import ModuleFeature, ModuleSetting, ModuleSettings
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


def _seed_inventory_settings():
    cache.clear()
    for key, default in (
        ('show_stock_movements', True),
        ('enable_stock_adjustments', True),
        ('enable_stock_purchases', True),
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


def _set_catalog_feature(module_name, feature_key, enabled):
    module, _ = ModuleSettings.objects.update_or_create(
        module_name=module_name,
        defaults={'description': module_name, 'is_enabled': True},
    )
    ModuleFeature.objects.update_or_create(
        module=module,
        feature_key=feature_key,
        defaults={
            'feature_name': feature_key,
            'description': '',
            'is_enabled': enabled,
            'display_order': 1,
        },
    )
    row = module.features.filter(feature_key=feature_key).first()
    if row and row.is_enabled != enabled:
        row.is_enabled = enabled
        row.save(update_fields=['is_enabled'])


class InventoryDualGateAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Dual Gate Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Dual Gate Product',
            sku='DG-001',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('60.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _seed_inventory_settings()
        SettingsService.set('inventory', 'enable_stock_adjustments', True)

    def test_adjust_forbidden_when_catalog_stock_adjustments_off(self):
        _set_catalog_feature('inventory', 'stock_adjustments', False)
        _set_catalog_feature('stock', 'stock_adjustments', False)
        response = self.client.post(
            '/api/inventory/adjust/',
            {'product_id': self.product.id, 'quantity': 1},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_adjust_allowed_when_both_gates_on(self):
        _set_catalog_feature('inventory', 'stock_adjustments', True)
        response = self.client.post(
            '/api/inventory/adjust/',
            {'product_id': self.product.id, 'quantity': 1, 'reason': 'test'},
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
