"""Tests for sales catalog rules helper."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import UserProfile, Role
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from products.catalog_rules import apply_sales_catalog_rules, sales_catalog_mode_active
from settings.models import StoreSettings


class CatalogRulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.sales_user = User.objects.create_user('catalog_sales', password='pass')
        sales_role = Role.objects.get(name=ROLE_SALES)
        UserProfile.objects.create(
            user=cls.sales_user,
            role='cashier',
            custom_role=sales_role,
            is_active=True,
        )
        store = StoreSettings.load()
        store.allow_sales_add_products = True
        store.sales_catalog_skip_pricing = True
        store.save()

    def test_sales_catalog_mode_active_for_sales_user(self):
        self.assertTrue(sales_catalog_mode_active(self.sales_user))

    def test_apply_rules_zeros_pricing_on_create(self):
        data = {'name': 'X', 'price': Decimal('99'), 'mrp': Decimal('120'), 'cost': Decimal('40')}
        apply_sales_catalog_rules(data, user=self.sales_user, is_create=True)
        self.assertEqual(data['price'], Decimal('0'))
        self.assertEqual(data['mrp'], Decimal('0'))
        self.assertEqual(data['cost'], Decimal('0'))

    def test_apply_rules_strips_pricing_on_update(self):
        data = {'name': 'Renamed', 'price': Decimal('50')}
        apply_sales_catalog_rules(data, user=self.sales_user, is_create=False)
        self.assertNotIn('price', data)
