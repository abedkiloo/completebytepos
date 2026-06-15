"""Unit tests for approved-only sellable state (effective.py)."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from approvals.effective import (
    apply_approved_product_overlay,
    apply_approved_variant_overlay,
    approved_sellable_stock_quantity,
    has_pending_product_price,
    sellable_price,
)
from approvals.models import PendingChange
from approvals.registry import ACTION_PRODUCT_PRICE, ACTION_PRODUCT_STOCK
from products.models import Category, Color, Product, ProductVariant, Size
from settings.models import StoreSettings
from settings.test_utils import disable_maker_checker, enable_maker_checker


class EffectiveStateTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        self.category = Category.objects.create(name='Eff Cat', is_active=True)
        self.product = Product.objects.create(
            name='Eff Product',
            sku='EFF-1',
            category=self.category,
            price=Decimal('100'),
            mrp=Decimal('120'),
            stock_quantity=20,
            is_active=True,
        )
        self.size = Size.objects.create(name='M', code='M', is_active=True)
        self.color = Color.objects.create(name='Red', is_active=True)
        self.variant = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            sku='EFF-1-M-R',
            price=Decimal('100'),
            mrp=Decimal('130'),
            stock_quantity=15,
            is_active=True,
        )

    def test_has_pending_product_price_false_when_maker_checker_disabled(self):
        enable_maker_checker()
        PendingChange.objects.create(
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            action_type=ACTION_PRODUCT_PRICE,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'price': '500.00'},
            made_by=User.objects.create_user('req', password='x'),
        )
        disable_maker_checker()
        self.assertFalse(has_pending_product_price(self.product.pk))

    def test_sellable_price_returns_live_db_value_with_pending_proposal(self):
        enable_maker_checker()
        PendingChange.objects.create(
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            action_type=ACTION_PRODUCT_PRICE,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'price': '500.00'},
            made_by=User.objects.create_user('req2', password='x'),
        )
        self.assertEqual(sellable_price(self.product), Decimal('100'))
        self.assertEqual(sellable_price(self.product, self.variant), Decimal('100'))

    def test_apply_approved_product_overlay_includes_proposed_values_on_pending_price(self):
        enable_maker_checker()
        PendingChange.objects.create(
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            action_type=ACTION_PRODUCT_PRICE,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'price': '140.00', 'mrp': '160.00'},
            made_by=User.objects.create_user('req3', password='x'),
        )
        data = {'id': self.product.pk, 'price': '100.00', 'mrp': '120.00'}
        out = apply_approved_product_overlay(self.product, data)
        self.assertTrue(out['pending_approval']['pending_price'])
        self.assertEqual(out['pending_approval']['proposed_values']['price'], '140.00')
        self.assertEqual(out['price'], '100.00')

    def test_apply_approved_variant_overlay_includes_proposed_mrp(self):
        enable_maker_checker()
        PendingChange.objects.create(
            entity_type='products.ProductVariant',
            entity_id=str(self.variant.pk),
            action_type=ACTION_PRODUCT_PRICE,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'mrp': '150.00'},
            made_by=User.objects.create_user('req4', password='x'),
        )
        data = {'id': self.variant.pk, 'price': '100.00', 'mrp': '130.00'}
        out = apply_approved_variant_overlay(self.variant, data)
        self.assertTrue(out['pending_approval']['pending_price'])
        self.assertEqual(out['pending_approval']['proposed_values']['mrp'], '150.00')
        self.assertEqual(out['mrp'], '130.00')

    def test_approved_sellable_stock_caps_from_pending_decrease(self):
        enable_maker_checker()
        PendingChange.objects.create(
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            action_type=ACTION_PRODUCT_STOCK,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'stock_quantity': 8},
            made_by=User.objects.create_user('req5', password='x'),
        )
        self.assertEqual(approved_sellable_stock_quantity(self.product), 8)

    def test_pending_stock_increase_does_not_raise_sellable_cap(self):
        enable_maker_checker()
        PendingChange.objects.create(
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            action_type=ACTION_PRODUCT_STOCK,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'stock_quantity': 100},
            made_by=User.objects.create_user('req6', password='x'),
        )
        self.assertEqual(approved_sellable_stock_quantity(self.product), 20)

    def test_variant_pending_stock_caps_sellable_quantity(self):
        enable_maker_checker()
        PendingChange.objects.create(
            entity_type='products.ProductVariant',
            entity_id=str(self.variant.pk),
            action_type=ACTION_PRODUCT_STOCK,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'stock_quantity': 5},
            made_by=User.objects.create_user('req7', password='x'),
        )
        self.assertEqual(
            approved_sellable_stock_quantity(self.product, self.variant),
            5,
        )

    def test_variant_product_aggregate_sellable_sums_per_variant_caps(self):
        enable_maker_checker()
        self.product.has_variants = True
        self.product.stock_quantity = 40
        self.product.save(update_fields=['has_variants', 'stock_quantity'])
        self.variant.stock_quantity = 25
        self.variant.save(update_fields=['stock_quantity'])
        sibling = ProductVariant.objects.create(
            product=self.product,
            size=Size.objects.create(name='S', code='S', is_active=True),
            color=self.color,
            sku='EFF-1-S-R',
            price=Decimal('100'),
            stock_quantity=15,
            is_active=True,
        )
        PendingChange.objects.create(
            entity_type='products.ProductVariant',
            entity_id=str(self.variant.pk),
            action_type=ACTION_PRODUCT_STOCK,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'stock_quantity': 5},
            made_by=User.objects.create_user('req8', password='x'),
        )
        self.assertEqual(approved_sellable_stock_quantity(self.product, self.variant), 5)
        self.assertEqual(approved_sellable_stock_quantity(self.product, sibling), 15)
        self.assertEqual(approved_sellable_stock_quantity(self.product), 20)
