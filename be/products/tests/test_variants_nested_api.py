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

    def test_create_product_with_nested_variants_includes_mrp(self):
        payload = {
            'name': 'API MRP Variant Product',
            'sku': 'API-VAR-MRP',
            'category': self.category.id,
            'has_variants': True,
            'track_stock': True,
            'variants': [
                {
                    'size': self.size.id,
                    'color': self.color.id,
                    'sku': 'API-VAR-MRP-DEF',
                    'stock_quantity': 2,
                    'price': '100.00',
                    'mrp': '130.00',
                }
            ],
        }

        resp = self.client.post('/api/products/', payload, format='json')
        self.assertIn(resp.status_code, (201, 202), msg=f'Got {resp.status_code} {resp.data}')

        product = Product.objects.filter(sku='API-VAR-MRP').first()
        self.assertIsNotNone(product)
        variant = product.variants.first()
        self.assertEqual(variant.mrp, Decimal('130.00'))