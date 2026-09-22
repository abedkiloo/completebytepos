from django.core.management import call_command
from django.test import TestCase

from products.models import Category, Product, ProductVariant, Size


class SeedUatSofaCatalogTests(TestCase):
    def test_seeds_sofa_craft_products_with_variants_and_zero_stock(self):
        call_command('seed_uat_sofa_catalog')

        products = Product.objects.filter(sku__startswith='UAT-SOFA-')
        self.assertGreaterEqual(products.count(), 15)
        self.assertTrue(products.filter(has_variants=True).exists())
        self.assertTrue(products.filter(has_variants=False).exists())
        self.assertFalse(products.exclude(stock_quantity=0).exists())

        velvet = Product.objects.get(sku='UAT-SOFA-VELVET')
        self.assertTrue(velvet.has_variants)
        variants = ProductVariant.objects.filter(product=velvet)
        self.assertEqual(variants.count(), 8)  # 2 widths × 4 colors
        self.assertFalse(variants.exclude(stock_quantity=0).exists())
        self.assertTrue(variants.filter(size__isnull=False, color__isnull=False).exists())

        foam = Product.objects.get(sku='UAT-SOFA-HD-FOAM')
        foam_variants = ProductVariant.objects.filter(product=foam)
        self.assertEqual(foam_variants.count(), 3)
        self.assertTrue(foam_variants.filter(color__isnull=True, size__isnull=False).exists())

        self.assertTrue(Category.objects.filter(name='UAT Sofa Craft').exists())
        self.assertTrue(Size.objects.filter(code='UAT-3S').exists())

    def test_seed_is_idempotent(self):
        call_command('seed_uat_sofa_catalog')
        first = Product.objects.filter(sku__startswith='UAT-SOFA-').count()
        call_command('seed_uat_sofa_catalog')
        self.assertEqual(Product.objects.filter(sku__startswith='UAT-SOFA-').count(), first)

    def test_revert_removes_only_uat_sofa_catalog(self):
        keeper = Product.objects.create(
            name='Keep me',
            sku='LIVE-KEEP',
            price=10,
            cost=5,
            stock_quantity=0,
        )
        call_command('seed_uat_sofa_catalog')
        self.assertTrue(Product.objects.filter(sku__startswith='UAT-SOFA-').exists())

        call_command('seed_uat_sofa_catalog', revert=True)

        self.assertFalse(Product.objects.filter(sku__startswith='UAT-SOFA-').exists())
        self.assertFalse(ProductVariant.objects.filter(sku__startswith='UAT-SOFA-').exists())
        self.assertFalse(Category.objects.filter(name='UAT Sofa Craft').exists())
        self.assertFalse(Size.objects.filter(code__startswith='UAT-').exists())
        self.assertTrue(Product.objects.filter(pk=keeper.pk).exists())
