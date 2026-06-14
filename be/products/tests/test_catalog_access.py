"""Granular product field access (module settings + role)."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ROLE_SUPER_ADMIN, sync_default_roles
from products.catalog_access import (
    products_sales_catalog_access_enabled,
    resolve_user_role,
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

    def test_manager_cost_kept_when_pricing_disabled_but_cost_enabled(self):
        _seed_products_access_settings(
            allow_manager_edit_pricing=False,
            allow_manager_edit_cost=True,
        )
        data = {'cost': Decimal('88'), 'price': Decimal('150')}
        strip_product_fields_by_access(
            data, user=self.manager, instance=self.product, is_create=False
        )
        self.assertIn('cost', data)
        self.assertEqual(data['cost'], Decimal('88'))
        self.assertNotIn('price', data)

    def test_sales_catalog_access_disabled_when_store_flag_off(self):
        store = StoreSettings.load()
        store.allow_sales_add_products = False
        store.save(update_fields=['allow_sales_add_products'])
        self.assertFalse(products_sales_catalog_access_enabled())

    def test_sales_catalog_access_disabled_when_module_flag_off(self):
        _seed_products_access_settings(allow_sales_catalog_access=False)
        self.assertFalse(products_sales_catalog_access_enabled())

    def test_resolve_user_role_superuser_and_custom_super_admin(self):
        admin = User.objects.create_superuser('su', 'su@t.com', 'pass')
        self.assertEqual(resolve_user_role(admin), 'super_admin')
        custom_admin = User.objects.create_user('cadmin', password='x')
        UserProfile.objects.create(
            user=custom_admin,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
        )
        self.assertEqual(resolve_user_role(custom_admin), 'super_admin')

    def test_resolve_user_role_anonymous_without_profile(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(resolve_user_role(AnonymousUser()), 'anonymous')
        no_profile = User.objects.create_user('nop', password='x')
        self.assertEqual(resolve_user_role(no_profile), 'anonymous')

    def test_sales_may_edit_stock_when_flags_on(self):
        _seed_products_access_settings(allow_sales_edit_stock=True)
        self.assertTrue(user_may_edit_product_stock(self.sales))

    def test_strip_on_create_zeros_pricing_for_sales(self):
        data = {'name': 'New', 'price': Decimal('200'), 'mrp': Decimal('250')}
        strip_product_fields_by_access(
            data, user=self.sales, instance=None, is_create=True
        )
        self.assertEqual(data['price'], Decimal('0'))
        self.assertEqual(data['mrp'], Decimal('0'))

    def test_manager_pricing_stripped_when_module_flag_off(self):
        _seed_products_access_settings(allow_manager_edit_pricing=False)
        data = {'price': Decimal('150'), 'mrp': Decimal('180')}
        strip_product_fields_by_access(
            data, user=self.manager, instance=self.product, is_create=False
        )
        self.assertNotIn('price', data)
        self.assertNotIn('mrp', data)
