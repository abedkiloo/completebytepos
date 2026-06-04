"""Sales staff must not change pricing, stock, or sale overrides."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, sync_default_roles
from accounts.sensitive_edits import (
    clamp_holding_financial_adjustments,
    strip_sensitive_product_fields,
    user_may_edit_financial_fields,
    validate_sale_unit_price_override,
)
from products.models import Category, Product


class SensitiveEditsPolicyTests(TestCase):
    def setUp(self):
        sync_default_roles()
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

    def test_sales_cannot_edit_financial_fields(self):
        self.assertFalse(user_may_edit_financial_fields(self.sales))
        self.assertTrue(user_may_edit_financial_fields(self.manager))

    def test_sales_product_update_strips_stock_and_pricing(self):
        data = {
            'price': Decimal('200'),
            'stock_quantity': 999,
            'low_stock_threshold': 1,
        }
        strip_sensitive_product_fields(
            data, user=self.sales, instance=self.product, is_create=False
        )
        self.assertNotIn('price', data)
        self.assertNotIn('stock_quantity', data)

    def test_sales_cannot_override_sale_unit_price(self):
        with self.assertRaises(ValidationError):
            validate_sale_unit_price_override(
                self.sales,
                product=self.product,
                variant=None,
                override=Decimal('1'),
            )

    def test_manager_may_override_sale_unit_price(self):
        validate_sale_unit_price_override(
            self.manager,
            product=self.product,
            variant=None,
            override=Decimal('99'),
        )

    def test_sales_holding_tax_discount_clamped(self):
        tax, disc = clamp_holding_financial_adjustments(
            self.sales, Decimal('10'), Decimal('5')
        )
        self.assertEqual(tax, Decimal('0'))
        self.assertEqual(disc, Decimal('0'))
