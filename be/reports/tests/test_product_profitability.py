"""Unit, integration, module, stress, security, and corrected tests for SKU profitability."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile
from accounts.role_definitions import (
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from products.models import Category, Product
from reports.product_profitability import (
    build_product_profitability_rows,
    margin_pct,
    normalize_product_sort,
    sort_product_rows,
)
from sales.models import Sale, SaleItem
from reports.sale_scope import posted_sale_items
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import SuperAdminAPITestCase


class ProductProfitabilityUnitTests(SuperAdminAPITestCase):
    def test_normalize_sort_aliases(self):
        self.assertEqual(normalize_product_sort('profit'), 'gross_profit')
        self.assertEqual(normalize_product_sort('margin'), 'margin_pct')
        self.assertEqual(normalize_product_sort('qty'), 'quantity')
        self.assertEqual(normalize_product_sort('nope'), 'revenue')

    def test_margin_pct(self):
        self.assertEqual(margin_pct(100, 40), 60.0)
        self.assertIsNone(margin_pct(0, 0))

    def test_sort_rows_by_gross_profit(self):
        rows = [
            {'name': 'A', 'gross_profit': 10, 'margin_pct': 50, 'revenue': 20, 'quantity_sold': 1},
            {'name': 'B', 'gross_profit': 50, 'margin_pct': 10, 'revenue': 500, 'quantity_sold': 9},
        ]
        ranked = sort_product_rows(rows, 'gross_profit')
        self.assertEqual([r['name'] for r in ranked], ['B', 'A'])


class ProductProfitabilityCorrectedTests(SuperAdminAPITestCase):
    """Corrected: rank by which goods earn more profit, with margin %."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        ModuleSettings.objects.update_or_create(
            module_name='reports',
            defaults={'description': 'reports', 'is_enabled': True},
        )
        cat = Category.objects.create(name='Prof Cat', is_active=True)
        self.high_profit = Product.objects.create(
            name='High Margin Zipper',
            sku='HM-1',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('20'),
            stock_quantity=100,
            is_active=True,
        )
        self.high_volume = Product.objects.create(
            name='Low Margin Bulk',
            sku='LM-1',
            category=cat,
            price=Decimal('50'),
            cost=Decimal('45'),
            stock_quantity=100,
            is_active=True,
        )
        now = timezone.now()
        sale = Sale.objects.create(
            sale_number='SALE-PROF-1',
            status='completed',
            cashier=self.admin,
            subtotal=Decimal('600'),
            total=Decimal('600'),
            amount_paid=Decimal('600'),
            payment_method='cash',
            occurred_at=now,
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.high_profit,
            quantity=2,
            unit_price=Decimal('100'),
            unit_cost=Decimal('20'),
            subtotal=Decimal('200'),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.high_volume,
            quantity=8,
            unit_price=Decimal('50'),
            unit_cost=Decimal('45'),
            subtotal=Decimal('400'),
        )

    def test_build_ranks_high_profit_first(self):
        qs = posted_sale_items().filter(sale__sale_number='SALE-PROF-1')
        rows, sort_key = build_product_profitability_rows(
            qs, sort='gross_profit', hub_keys=True
        )
        self.assertEqual(sort_key, 'gross_profit')
        self.assertEqual(rows[0]['product_id'], self.high_profit.id)
        self.assertEqual(rows[0]['gross_profit'], 160.0)
        self.assertEqual(rows[0]['margin_pct'], 80.0)
        self.assertEqual(rows[1]['product_id'], self.high_volume.id)
        self.assertEqual(rows[1]['gross_profit'], 40.0)

    def test_api_products_sort_gross_profit(self):
        resp = self.client.get(
            '/api/reports/products/',
            {'sort': 'gross_profit', 'limit': 10},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['sort'], 'gross_profit')
        top = resp.data['top']
        self.assertGreaterEqual(len(top), 2)
        self.assertEqual(top[0]['product__id'], self.high_profit.id)
        self.assertIn('margin_pct', top[0])

    def test_api_top_products_sort_gross_profit(self):
        resp = self.client.get(
            '/api/reports/top_products/',
            {'period': 'month', 'sort': 'gross_profit', 'limit': 5},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['sort'], 'gross_profit')
        self.assertEqual(resp.data['items'][0]['product_id'], self.high_profit.id)


class ProductProfitabilityModuleTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        self.mod, _ = ModuleSettings.objects.update_or_create(
            module_name='reports',
            defaults={'description': 'reports', 'is_enabled': True},
        )

    def test_feature_row_can_disable_product_profitability(self):
        feat, _ = ModuleFeature.objects.update_or_create(
            module=self.mod,
            feature_key='product_profitability',
            defaults={
                'feature_name': 'Product profitability',
                'is_enabled': False,
            },
        )
        self.assertFalse(feat.is_enabled)


class ProductProfitabilityStressTests(SuperAdminAPITestCase):
    def test_many_skus_sort_stable(self):
        rows = [
            {
                'name': f'P{i}',
                'gross_profit': float(i % 17),
                'margin_pct': float((i * 3) % 100),
                'revenue': float(i + 1),
                'quantity_sold': i,
            }
            for i in range(300)
        ]
        ranked = sort_product_rows(rows, 'gross_profit')
        self.assertEqual(len(ranked), 300)
        profits = [r['gross_profit'] for r in ranked]
        self.assertEqual(profits, sorted(profits, reverse=True))


class ProductProfitabilitySecurityTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        ModuleSettings.objects.update_or_create(
            module_name='reports',
            defaults={'description': 'reports', 'is_enabled': True},
        )

    def test_unauthenticated_denied(self):
        self.client.credentials()
        resp = self.client.get('/api/reports/products/', {'sort': 'gross_profit'})
        self.assertIn(resp.status_code, (401, 403))

    def test_sales_without_reports_view_denied(self):
        roles = sync_default_roles(created_by=self.admin)
        sales_user = User.objects.create_user('prof_sales', password='x')
        UserProfile.objects.create(
            user=sales_user,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        client = APIClient()
        token = RefreshToken.for_user(sales_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.get('/api/reports/products/', {'sort': 'gross_profit'})
        self.assertIn(resp.status_code, (403, 401))
