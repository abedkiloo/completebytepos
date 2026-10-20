"""API coverage for products view actions still missing lines."""

from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core.cache import cache
from rest_framework import status

from products.models import Category, Product
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import SuperAdminAPITestCase


def _seed_flags():
    cache.clear()
    for key, default in (
        ('show_status', True),
        ('show_cost_price', True),
        ('show_mrp', True),
        ('show_sku_in_list', True),
        ('show_low_stock_badges', True),
        ('enable_bulk_operations', True),
        ('enable_csv_import_export', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='products',
            key=key,
            defaults={'label': key, 'description': '', 'default_value': default, 'value': default},
        )


class ProductViewsAPICoverageTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        disable_maker_checker()
        _seed_flags()
        self.category = Category.objects.create(name='ViewAPI Cat', is_active=True)
        self.product = Product.objects.create(
            name='ViewAPI Product',
            sku='VAPI-1',
            category=self.category,
            price=Decimal('40'),
            cost=Decimal('15'),
            stock_quantity=2,
            low_stock_threshold=5,
            track_stock=True,
            is_active=True,
        )

    def test_search_check_duplicate_stats_stock_lists(self):
        empty = self.client.get('/api/products/search/')
        self.assertEqual(empty.status_code, status.HTTP_200_OK)

        found = self.client.get('/api/products/search/', {'q': 'ViewAPI', 'limit': 'bad'})
        self.assertEqual(found.status_code, status.HTTP_200_OK)
        self.assertTrue(len(found.data) >= 1)

        big = self.client.get('/api/products/search/', {'q': 'ViewAPI', 'limit': '5000'})
        self.assertEqual(big.status_code, status.HTTP_200_OK)

        with patch(
            'products.services.ProductService.search_products',
            side_effect=RuntimeError('search fail'),
        ):
            err = self.client.get('/api/products/search/', {'q': 'x'})
            self.assertEqual(err.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        none = self.client.get('/api/products/check_duplicate/', {'name': 'No Such Name'})
        self.assertEqual(none.status_code, status.HTTP_200_OK)
        self.assertIsNone(none.data.get('duplicate'))

        dup = self.client.get(
            '/api/products/check_duplicate/',
            {'name': self.product.name, 'exclude': 'bad'},
        )
        self.assertEqual(dup.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(dup.data.get('duplicate'))

        stats = self.client.get('/api/products/statistics/')
        self.assertEqual(stats.status_code, status.HTTP_200_OK)

        with patch(
            'products.services.ProductService.get_product_statistics',
            side_effect=RuntimeError('stats fail'),
        ):
            bad_stats = self.client.get('/api/products/statistics/')
            self.assertEqual(bad_stats.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        low = self.client.get('/api/products/low_stock/')
        self.assertEqual(low.status_code, status.HTTP_200_OK)
        out = self.client.get('/api/products/out_of_stock/')
        self.assertEqual(out.status_code, status.HTTP_200_OK)

    def test_bulk_ops_and_csv(self):
        other = Product.objects.create(
            name='Bulk Other', sku='VAPI-2', category=self.category,
            price=Decimal('10'), stock_quantity=1, is_active=False,
        )
        upd = self.client.post(
            '/api/products/bulk_update/',
            {'product_ids': [other.id], 'update_data': {'description': 'bulk'}},
            format='json',
        )
        self.assertEqual(upd.status_code, status.HTTP_200_OK, upd.data)

        with patch(
            'products.services.ProductService.bulk_update_products',
            side_effect=RuntimeError('bulk fail'),
        ):
            fail = self.client.post(
                '/api/products/bulk_update/',
                {'product_ids': [other.id], 'update_data': {'description': 'x'}},
                format='json',
            )
            self.assertEqual(fail.status_code, status.HTTP_400_BAD_REQUEST)

        act = self.client.post(
            '/api/products/bulk_activate/',
            {'product_ids': [other.id]},
            format='json',
        )
        self.assertEqual(act.status_code, status.HTTP_200_OK)

        empty_ids = self.client.post('/api/products/bulk_activate/', {'product_ids': []}, format='json')
        self.assertEqual(empty_ids.status_code, status.HTTP_400_BAD_REQUEST)

        deact = self.client.post(
            '/api/products/bulk_deactivate/',
            {'product_ids': [other.id]},
            format='json',
        )
        self.assertEqual(deact.status_code, status.HTTP_200_OK)

        empty_deact = self.client.post('/api/products/bulk_deactivate/', {}, format='json')
        self.assertEqual(empty_deact.status_code, status.HTTP_400_BAD_REQUEST)

        empty_del = self.client.post('/api/products/bulk_delete/', {'product_ids': []}, format='json')
        self.assertEqual(empty_del.status_code, status.HTTP_400_BAD_REQUEST)

        # product not in use — can delete
        unused = Product.objects.create(
            name='Delete Me', sku='VAPI-DEL', category=self.category,
            price=Decimal('1'), is_active=True,
        )
        deleted = self.client.post(
            '/api/products/bulk_delete/',
            {'product_ids': [unused.id]},
            format='json',
        )
        self.assertEqual(deleted.status_code, status.HTTP_200_OK, deleted.data)

        export = self.client.get('/api/products/export/')
        self.assertEqual(export.status_code, status.HTTP_200_OK)

        csv_body = (
            'SKU,Name,Barcode,Category,Subcategory,MRP,Selling Price,Cost,Stock Quantity,'
            'Low Stock Threshold,Unit,Has Variants,Track Stock,Is Taxable,Is Active,Description,Supplier\n'
            'VAPI-IMP,Imported ViewAPI,,ViewAPI Cat,,20,15,5,3,1,piece,False,True,True,True,,\n'
        )
        uploaded = BytesIO(csv_body.encode())
        uploaded.name = 'products.csv'
        imported = self.client.post(
            '/api/products/import_csv/',
            {'file': uploaded},
            format='multipart',
        )
        self.assertEqual(imported.status_code, status.HTTP_200_OK, imported.data)

        SettingsService.set('products', 'enable_bulk_operations', False)
        blocked = self.client.post(
            '/api/products/bulk_activate/',
            {'product_ids': [self.product.id]},
            format='json',
        )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)

        SettingsService.set('products', 'enable_csv_import_export', False)
        blocked_export = self.client.get('/api/products/export/')
        self.assertEqual(blocked_export.status_code, status.HTTP_403_FORBIDDEN)
