"""Unit tests for product stock history trail (debt-ledger style)."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from inventory.models import StockMovement
from inventory.stock_history import (
    product_stock_history_allowed,
    record_opening_stock_movement,
    stock_flow_for_movement,
    user_is_stock_history_admin,
)
from products.models import Category, Product
from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from utils.tests.module_setting_helpers import enable_inventory_api_features
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from django.core.cache import cache


class StockFlowUnitTests(TestCase):
    def setUp(self):
        ensure_permissions()
        sync_default_roles()
        enable_inventory_api_features()
        self.cat = Category.objects.create(name='Flow Cat', is_active=True)
        self.user = User.objects.create_user(
            username='cashier_k',
            password='x',
            first_name='User',
            last_name='K',
        )
        self.product = Product.objects.create(
            name='Trail Widget',
            sku='TRAIL-001',
            category=self.cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=0,
            track_stock=True,
            is_active=True,
        )

    def test_sale_trail_reads_like_debt_payment(self):
        self.product.stock_quantity = 400
        self.product.save(update_fields=['stock_quantity'])
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type='sale',
            quantity=45,
            user=self.user,
            reference='SALE-1',
        )
        trail = stock_flow_for_movement(movement)
        self.assertEqual(trail['previous_stock'], 400)
        self.assertEqual(trail['change_qty'], -45)
        self.assertEqual(trail['new_stock'], 355)
        self.assertEqual(trail['change_label'], 'Sold 45')
        self.assertIn('Previous stock 400', trail['stock_flow'])
        self.assertIn('Sold 45', trail['stock_flow'])
        self.assertIn('New stock 355', trail['stock_flow'])
        self.assertIn('by User K', trail['stock_flow'])

    def test_opening_stock_creates_purchase_from_zero(self):
        self.product.stock_quantity = 400
        self.product.save(update_fields=['stock_quantity'])
        movement = record_opening_stock_movement(product=self.product, user=self.user)
        self.assertIsNotNone(movement)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 400)
        self.assertEqual(movement.reference, 'OPENING')
        trail = stock_flow_for_movement(movement)
        self.assertEqual(trail['previous_stock'], 0)
        self.assertEqual(trail['new_stock'], 400)
        self.assertEqual(trail['change_label'], 'Received 400')

    def test_opening_stock_idempotent(self):
        self.product.stock_quantity = 10
        self.product.save(update_fields=['stock_quantity'])
        first = record_opening_stock_movement(product=self.product, user=self.user)
        second = record_opening_stock_movement(product=self.product, user=self.user)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(
            StockMovement.objects.filter(product=self.product, reference='OPENING').count(),
            1,
        )


class StockHistoryAccessUnitTests(TestCase):
    def setUp(self):
        ensure_permissions()
        sync_default_roles()
        enable_inventory_api_features()
        self.manager = User.objects.create_user(username='mgr_hist', password='x')
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        self.cashier = User.objects.create_user(username='cash_hist', password='x')
        UserProfile.objects.create(
            user=self.cashier,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def test_manager_allowed_when_config_on(self):
        self.assertTrue(user_is_stock_history_admin(self.manager))
        self.assertTrue(product_stock_history_allowed(self.manager))

    def test_cashier_blocked(self):
        self.assertFalse(user_is_stock_history_admin(self.cashier))
        self.assertFalse(product_stock_history_allowed(self.cashier))

    def test_config_off_blocks_manager(self):
        cache.clear()
        ModuleSetting.objects.update_or_create(
            module='inventory',
            key='show_product_stock_history',
            defaults={
                'label': 'Show product stock history',
                'default_value': False,
                'value': False,
            },
        )
        SettingsService.set('inventory', 'show_product_stock_history', False)
        self.assertFalse(product_stock_history_allowed(self.manager))
