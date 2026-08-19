"""Tests for variant-aware stock alert rules."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from products.models import Category, Color, Product, ProductVariant, Size
from products.services import ProductService
from products.stock_alerts import (
    apply_low_stock_filter,
    apply_out_of_stock_filter,
    count_stock_alert_items,
    product_has_low_stock,
    product_has_out_of_stock,
    variant_effective_threshold,
    variant_is_low_stock,
    variant_is_out_of_stock,
)
from settings.models import Tenant


class StockAlertsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='stock_alerts', password='x')
        self.tenant = Tenant.objects.create(
            name='Stock Alerts Tenant',
            code='STA',
            owner=self.user,
            created_by=self.user,
        )
        self.category = Category.objects.create(name='Apparel', is_active=True)
        self.size_l = Size.objects.create(name='Large', code='L', display_order=1, is_active=True)
        self.size_s = Size.objects.create(name='Small', code='S', display_order=2, is_active=True)
        self.color_black = Color.objects.create(name='Black', hex_code='#000000', is_active=True)
        self.color_grey = Color.objects.create(name='Grey', hex_code='#888888', is_active=True)
        self.service = ProductService()

    def _variant_product(self):
        product = Product.objects.create(
            name='Hook Loop',
            sku='HL-001',
            category=self.category,
            price=Decimal('400.00'),
            cost=Decimal('295.00'),
            has_variants=True,
            track_stock=True,
            low_stock_threshold=10,
            stock_quantity=110,
            is_active=True,
        )
        ProductVariant.objects.create(
            product=product,
            size=self.size_l,
            color=self.color_black,
            sku='HL-001-BLA',
            price=Decimal('400.00'),
            stock_quantity=0,
            low_stock_threshold=10,
            is_active=True,
        )
        grey = ProductVariant.objects.create(
            product=product,
            size=self.size_s,
            color=self.color_grey,
            sku='HL-001-GRE',
            price=Decimal('400.00'),
            stock_quantity=110,
            low_stock_threshold=10,
            is_active=True,
        )
        product.stock_quantity = 110
        product.save(update_fields=['stock_quantity'])
        return product, grey

    def test_variant_out_of_stock_while_parent_total_is_positive(self):
        product, _grey = self._variant_product()
        self.assertFalse(product.stock_quantity == 0)
        self.assertTrue(product_has_out_of_stock(product))
        self.assertFalse(product_has_low_stock(product))

        counts = count_stock_alert_items()
        self.assertEqual(counts['out_of_stock_variant_count'], 1)
        self.assertEqual(counts['out_of_stock_simple_count'], 0)
        self.assertEqual(counts['out_of_stock_count'], 1)

        filtered = apply_out_of_stock_filter(Product.objects.all())
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().id, product.id)

    def test_variant_low_stock_is_counted_separately_from_parent_total(self):
        product, grey = self._variant_product()
        grey.stock_quantity = 4
        grey.save(update_fields=['stock_quantity'])
        product.stock_quantity = 4
        product.save(update_fields=['stock_quantity'])

        self.assertTrue(variant_is_low_stock(grey))
        self.assertFalse(variant_is_out_of_stock(grey))
        self.assertTrue(product_has_low_stock(product))

        counts = count_stock_alert_items()
        self.assertEqual(counts['low_stock_variant_count'], 1)
        self.assertEqual(counts['low_stock_count'], 1)

        filtered = apply_low_stock_filter(Product.objects.all())
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().id, product.id)

    def test_simple_product_alerts_still_work(self):
        low = Product.objects.create(
            name='Simple Low',
            sku='S-LOW',
            category=self.category,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=3,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True,
        )
        out = Product.objects.create(
            name='Simple Out',
            sku='S-OUT',
            category=self.category,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=0,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True,
        )

        self.assertTrue(product_has_low_stock(low))
        self.assertTrue(product_has_out_of_stock(out))

        counts = count_stock_alert_items()
        self.assertEqual(counts['low_stock_simple_count'], 1)
        self.assertEqual(counts['out_of_stock_simple_count'], 1)

    def test_statistics_include_variant_rows(self):
        self._variant_product()
        stats = self.service.get_product_statistics()
        self.assertEqual(stats['out_of_stock_count'], 1)
        self.assertEqual(stats['out_of_stock_variant_count'], 1)

    def test_build_queryset_out_of_stock_includes_variant_parent(self):
        product, _grey = self._variant_product()
        queryset = self.service.build_queryset({'out_of_stock': 'true'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().id, product.id)

    def test_build_queryset_low_stock_excludes_zero_stock_variants(self):
        product, grey = self._variant_product()
        grey.stock_quantity = 0
        grey.save(update_fields=['stock_quantity'])

        queryset = self.service.build_queryset({'low_stock': 'true'})
        self.assertEqual(queryset.count(), 0)

        queryset = self.service.build_queryset({'out_of_stock': 'true'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().id, product.id)

    def test_variant_can_use_its_own_threshold(self):
        product, grey = self._variant_product()
        ProductVariant.objects.filter(product=product, stock_quantity=0).update(stock_quantity=5)
        grey.low_stock_threshold = 2
        grey.stock_quantity = 2
        grey.save(update_fields=['low_stock_threshold', 'stock_quantity'])

        self.assertTrue(variant_is_low_stock(grey))
        self.assertFalse(product_has_out_of_stock(product))

        product.refresh_from_db()
        product._prefetched_objects_cache = {'variants': list(product.variants.all())}
        self.assertTrue(product_has_low_stock(product))

    def test_untracked_products_are_ignored(self):
        product = Product.objects.create(
            name='Service item',
            sku='SVC-1',
            category=self.category,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            track_stock=False,
            stock_quantity=0,
            is_active=True,
        )
        self.assertFalse(product_has_out_of_stock(product))
        self.assertFalse(product_has_low_stock(product))
        counts = count_stock_alert_items(Product.objects.filter(pk=product.pk))
        self.assertEqual(counts['out_of_stock_count'], 0)
        self.assertEqual(counts['low_stock_count'], 0)

    def test_helper_edge_cases(self):
        product, grey = self._variant_product()
        grey.low_stock_threshold = None
        grey.stock_quantity = 5
        grey.save(update_fields=['low_stock_threshold', 'stock_quantity'])
        self.assertEqual(variant_effective_threshold(grey), product.low_stock_threshold)
        self.assertFalse(variant_is_low_stock(ProductVariant.objects.get(stock_quantity=0)))

        simple = Product.objects.create(
            name='Simple Low',
            sku='SIMPLE-LOW',
            category=self.category,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=4,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True,
        )
        self.assertTrue(product_has_low_stock(simple))
        simple.stock_quantity = 0
        simple.save(update_fields=['stock_quantity'])
        self.assertFalse(product_has_low_stock(simple))

        product.refresh_from_db()
        product._prefetched_objects_cache = {'variants': list(product.variants.all())}
        self.assertTrue(product_has_out_of_stock(product))
