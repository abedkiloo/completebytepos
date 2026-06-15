from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Category, Color, Product, ProductVariant, Size
from settings.test_utils import enable_product_variants


class NestedVariantsAPITests(TestCase):
    def setUp(self):
        enable_product_variants()
        self.user = User.objects.create_superuser(
            username='api-admin', email='api@test.com', password='admin123'
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

        self.category = Category.objects.create(name='API Cat', is_active=True)
        self.size = Size.objects.create(name='Default', code='DEF', is_active=True)
        self.color = Color.objects.create(name='Default', is_active=True)

    def test_create_product_with_nested_variants_creates_variants_and_syncs_stock(self):
        payload = {
            'name': 'API Variant Product',
            'sku': 'API-VAR-1',
            'category': self.category.id,
            'has_variants': True,
            'track_stock': True,
            'variants': [
                {
                    'size': self.size.id,
                    'color': self.color.id,
                    'sku': 'API-VAR-1-DEF',
                    'stock_quantity': 5,
                    'price': '100.00',
                }
            ],
        }

        resp = self.client.post('/api/products/', payload, format='json')
        self.assertIn(resp.status_code, (201, 202), msg=f'Got {resp.status_code} {resp.data}')

        # If maker-checker queued the change, fetch created product by SKU
        product = Product.objects.filter(sku='API-VAR-1').first()
        self.assertIsNotNone(product)
        variants = list(product.variants.all())
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].stock_quantity, 5)
        # Parent stock must be synced from variants
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 5)

    def test_update_product_with_nested_variants_updates_and_creates_variants(self):
        # Create initial product with one variant
        product = Product.objects.create(
            name='Update Variant Product',
            sku='API-VAR-2',
            category=self.category,
            price=Decimal('50.00'),
            track_stock=True,
            has_variants=True,
            stock_quantity=0,
            is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=product,
            size=self.size,
            color=self.color,
            sku='API-VAR-2-DEF',
            stock_quantity=2,
            price=Decimal('50.00'),
            is_active=True,
        )
        # PATCH with updated existing variant and a new variant
        payload = {
            'variants': [
                {
                    'id': variant.id,
                    'stock_quantity': 3,
                },
                {
                    'size': self.size.id,
                    'color': self.color.id,
                    'sku': 'API-VAR-2-DEF-NEW',
                    'stock_quantity': 4,
                    'price': '60.00',
                },
            ],
        }

        resp = self.client.patch(f'/api/products/{product.id}/', payload, format='json')
        self.assertIn(resp.status_code, (200, 202), msg=f'Got {resp.status_code} {resp.data}')

        product.refresh_from_db()
        variants = list(product.variants.order_by('id').all())
        # Two variants should now exist
        self.assertEqual(len(variants), 2)
        # Stock sync: parent = sum(3 + 4) = 7
        self.assertEqual(product.stock_quantity, 7)