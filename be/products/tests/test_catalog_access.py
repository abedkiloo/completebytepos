"""Granular product field access (module settings + role)."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, sync_default_roles
from products.catalog_access import (
    strip_product_fields_by_access,
    user_may_edit_product_cost,
    user_may_edit_product_pricing,
    user_may_edit_product_stock,
)
from products.models import Category, Product
from settings.models import ModuleSetting, StoreSettings


def _seed_products_access_settings(**overrides):
    cache.clear()
    defaults = {
        'allow_sales_catalog_access': True,
        'allow_sales_edit_catalog_details': True,
        'allow_sales_edit_pricing': False,
        'allow_sales_edit_cost': False,
        'allow_sales_edit_stock': False,
        'allow_manager_edit_pricing': True,
        'allow_manager_edit_cost': False,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        ModuleSetting.objects.update_or_create(
            module='products',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': value,
                'value': value,
            },
        )


class CatalogAccessTests(TestCase):
    def setUp(self):
        sync_default_roles()
        _seed_products_access_settings()
        store = StoreSettings.load()
        store.allow_sales_add_products = True
        store.save()

        self.manager = User.objects.create_user('mgr', password='mgr123')
        self.sales = User.objects.create_user('sales', password='sales123')
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
        )
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )
        self.category = Category.objects.create(name='Cat', is_active=True)
        self.product = Product.objects.create(
            name='Item',
            sku='IT-1',
            category=self.category,
            price=Decimal('100'),
            mrp=Decimal('120'),
            cost=Decimal('50'),
            stock_quantity=25,
            is_active=True,
        )

    def test_manager_may_edit_pricing_but_not_cost_by_default(self):
        self.assertTrue(user_may_edit_product_pricing(self.manager))
        self.assertFalse(user_may_edit_product_cost(self.manager))
        self.assertTrue(user_may_edit_product_stock(self.manager))

    def test_sales_cannot_edit_pricing_cost_or_stock_by_default(self):
        self.assertFalse(user_may_edit_product_pricing(self.sales))
        self.assertFalse(user_may_edit_product_cost(self.sales))
        self.assertFalse(user_may_edit_product_stock(self.sales))

    def test_manager_cost_stripped_when_flag_off(self):
        data = {'cost': Decimal('99'), 'price': Decimal('150')}
        strip_product_fields_by_access(
            data, user=self.manager, instance=self.product, is_create=False
        )
        self.assertNotIn('cost', data)
        self.assertIn('price', data)

    def test_sales_update_strips_pricing_and_stock(self):
        data = {
            'price': Decimal('200'),
            'cost': Decimal('10'),
            'stock_quantity': 999,
        }
        strip_product_fields_by_access(
            data, user=self.sales, instance=self.product, is_create=False
        )
        self.assertNotIn('price', data)
        self.assertNotIn('cost', data)
        self.assertNotIn('stock_quantity', data)

    def test_sales_may_edit_pricing_when_module_flag_on(self):
        _seed_products_access_settings(allow_sales_edit_pricing=True)
        self.assertTrue(user_may_edit_product_pricing(self.sales))

    def test_manager_may_edit_cost_when_module_flag_on(self):
        _seed_products_access_settings(allow_manager_edit_cost=True)
        self.assertTrue(user_may_edit_product_cost(self.manager))
