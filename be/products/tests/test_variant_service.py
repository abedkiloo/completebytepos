from django.test import TransactionTestCase

from products.models import Product, Size, Color, ProductVariant
from products.services import ProductVariantService


class VariantServiceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.variant_service = ProductVariantService()

    def test_regenerate_creates_variants_and_syncs_stock(self):
        # Create product with variants enabled
        product = Product.objects.create(
            name='T-Shirt', sku='TSHIRT', price=100, cost=50,
            stock_quantity=5, has_variants=True, track_stock=True
        )

        # Create sizes and colors
        s1 = Size.objects.create(name='Small', code='S')
        s2 = Size.objects.create(name='Medium', code='M')
        c1 = Color.objects.create(name='Red')
        c2 = Color.objects.create(name='Blue')

        # Create an old variant to ensure deletion happens
        old = ProductVariant.objects.create(
            product=product, sku='TSHIRT-OLD', stock_quantity=10, price=90
        )

        # Regenerate variants atomically
        created = self.variant_service.regenerate_variants_atomic(
            product, sizes=[s1.id, s2.id], colors=[c1.id, c2.id]
        )

        # Expect 4 variants (2 sizes x 2 colors)
        self.assertEqual(ProductVariant.objects.filter(product=product).count(), 4)

        # Parent stock should be sum of variant stocks (all zero by default)
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 0)

        # Created list should reflect created variants
        self.assertEqual(len(created), 4)

    def test_regenerate_clears_variants_when_feature_disabled(self):
        # Product with variants previously present
        product = Product.objects.create(
            name='Hat', sku='HAT', price=20, cost=10,
            stock_quantity=5, has_variants=False, track_stock=True
        )

        # Add existing variants (should be removed)
        pv = ProductVariant.objects.create(product=product, sku='HAT-1', stock_quantity=3)

        # Call regenerate with no sizes/colors and has_variants False
        created = self.variant_service.regenerate_variants_atomic(product, sizes=None, colors=None)

        # Variants should be deleted
        self.assertEqual(ProductVariant.objects.filter(product=product).count(), 0)
        # No created variants returned
        self.assertEqual(created, [])
