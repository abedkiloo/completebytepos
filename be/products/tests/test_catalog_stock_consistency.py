"""
Regression: catalogue stock must match across list, search, detail, and sellable_stock_quantity.

Repro: has_variants=True, variants feature off, parent stock=400, variant rows=0
→ list showed 0, edit form showed 400.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Category, Color, Product, ProductVariant, Size
from products.serializers import (
    ProductListSerializer,
    ProductSearchSerializer,
    ProductSerializer,
)
from products.stock_utils import (
    apply_catalog_variant_representation,
    sellable_stock_quantity,
    variants_sold_as_simple,
)
from settings.test_utils import disable_product_variants
from utils.tests.module_setting_helpers import enable_products_list_api_fields


def _variant_product_fixture():
    disable_product_variants()
    category = Category.objects.create(name='General', is_active=True)
    product = Product.objects.create(
        name='Variant',
        sku='VAR-STOCK-1',
        category=category,
        mrp=Decimal('500'),
        price=Decimal('500'),
        cost=Decimal('300'),
        stock_quantity=400,
        track_stock=True,
        has_variants=True,
        is_active=True,
    )
    size = Size.objects.create(name='Default', code='DEF', is_active=True)
    color = Color.objects.create(name='Default', is_active=True)
    ProductVariant.objects.create(
        product=product,
        size=size,
        color=color,
        sku='VAR-STOCK-1-DEF',
        stock_quantity=0,
        is_active=True,
    )
    return product


class CatalogStockSerializerContractTests(TestCase):
    def setUp(self):
        self.product = _variant_product_fixture()

    def _stock_from(self, serializer_class):
        data = serializer_class(self.product).data
        return int(data['stock_quantity']), data['has_variants']

    def test_variants_sold_as_simple(self):
        self.assertTrue(variants_sold_as_simple(self.product))

    def test_sellable_stock_matches_parent_when_variant_rows_zero(self):
        self.assertEqual(sellable_stock_quantity(self.product), 400)

    def test_list_search_and_detail_expose_same_sellable_stock(self):
        expected = sellable_stock_quantity(self.product)
        for serializer_class in (
            ProductListSerializer,
            ProductSearchSerializer,
            ProductSerializer,
        ):
            stock, has_variants = self._stock_from(serializer_class)
            self.assertFalse(
                has_variants,
                f'{serializer_class.__name__} should hide variants when feature is off',
            )
            self.assertEqual(
                stock,
                expected,
                f'{serializer_class.__name__} stock must use sellable_stock_quantity',
            )

    def test_apply_catalog_variant_representation_matches_helper(self):
        raw = {'stock_quantity': 0, 'has_variants': True, 'price': '500'}
        out = apply_catalog_variant_representation(self.product, raw)
        self.assertEqual(int(out['stock_quantity']), 400)
        self.assertFalse(out['has_variants'])

    def test_sellable_stock_is_max_of_parent_and_variant_sum(self):
        self.product.stock_quantity = 5
        self.product.save()
        variant = self.product.variants.first()
        variant.stock_quantity = 10
        variant.save()
        self.assertEqual(sellable_stock_quantity(self.product), 10)
        self.assertEqual(
            int(ProductListSerializer(self.product).data['stock_quantity']),
            10,
        )


class CatalogStockAPIConsistencyTests(TestCase):
    def setUp(self):
        enable_products_list_api_fields()
        disable_product_variants()
        self.user = User.objects.create_superuser(
            username='stock-admin',
            email='stock@test.com',
            password='admin123',
        )
        self.product = _variant_product_fixture()
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_list_and_retrieve_api_stock_match(self):
        list_resp = self.client.get('/api/products/', {'search': 'Variant'})
        self.assertEqual(list_resp.status_code, 200)
        rows = list_resp.data.get('results', list_resp.data)
        row = next(p for p in rows if p['id'] == self.product.id)

        detail_resp = self.client.get(f'/api/products/{self.product.id}/')
        self.assertEqual(detail_resp.status_code, 200)

        self.assertEqual(int(row['stock_quantity']), 400)
        self.assertEqual(int(detail_resp.data['stock_quantity']), 400)
        self.assertEqual(row['stock_quantity'], detail_resp.data['stock_quantity'])

    def test_search_api_stock_matches_list(self):
        search_resp = self.client.get('/api/products/search/', {'q': 'VAR-STOCK'})
        self.assertEqual(search_resp.status_code, 200)
        hit = next(p for p in search_resp.data if p['id'] == self.product.id)
        self.assertEqual(int(hit['stock_quantity']), 400)
