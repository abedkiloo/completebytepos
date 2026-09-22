from django.core.management import call_command
from django.test import TestCase

from products.models import Category, Product, ProductVariant, Size
from products.stock_alerts import product_has_low_stock, product_has_out_of_stock


class SeedUatSofaCatalogTests(TestCase):
    def test_seeds_sofa_craft_products_with_mixed_stock(self):
        call_command('seed_uat_sofa_catalog')

        products = list(Product.objects.filter(sku__startswith='UAT-SOFA-'))
        self.assertGreaterEqual(len(products), 15)
        self.assertTrue(any(p.has_variants for p in products))
        self.assertTrue(any(not p.has_variants for p in products))

        out_skus = {'UAT-SOFA-DACRON', 'UAT-SOFA-WOOD-GLUE', 'UAT-SOFA-FAUX-LEATHER'}
        low_skus = {
            'UAT-SOFA-STAPLES',
            'UAT-SOFA-WEBBING',
            'UAT-SOFA-PIPING',
            'UAT-SOFA-THROW-COVER',
        }
        out = [p for p in products if product_has_out_of_stock(p)]
        low = [
            p for p in products
            if product_has_low_stock(p) and not product_has_out_of_stock(p)
        ]
        ok = [
            p for p in products
            if not product_has_out_of_stock(p) and not product_has_low_stock(p)
        ]

        self.assertEqual({p.sku for p in out}, out_skus)
        self.assertEqual({p.sku for p in low}, low_skus)
        self.assertEqual(len(out), 3)
        self.assertEqual(len(low), 4)
        self.assertGreater(len(ok), 0)

        velvet = Product.objects.get(sku='UAT-SOFA-VELVET')
        variants = ProductVariant.objects.filter(product=velvet)
        self.assertEqual(variants.count(), 8)
        self.assertTrue(variants.filter(stock_quantity__gt=5).exists())
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
