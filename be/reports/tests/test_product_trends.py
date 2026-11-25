"""
Unit, integration, module, stress, corrected, and security tests for product trends.
"""

from datetime import date, datetime
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import StockMovement
from products.models import Category, Product
from reports.product_trends import (
    build_product_trends,
    product_trends_allowed,
    product_trends_feature_enabled,
)
from sales.models import Sale, SaleItem
from settings.models import ModuleFeature, ModuleSetting, ModuleSettings
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


def _seed_product_report_settings(*, product_reports=True):
    cache.clear()
    ModuleSetting.objects.update_or_create(
        module='reports',
        key='enable_product_reports',
        defaults={
            'label': 'Product reports',
            'description': '',
            'default_value': True,
            'value': product_reports,
        },
    )


def _set_product_trends_feature(enabled: bool):
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='reports',
        defaults={'is_enabled': True, 'description': 'reports'},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feature, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key='product_trends',
        defaults={'feature_name': 'Product trends', 'is_enabled': enabled},
    )
    feature.is_enabled = enabled
    feature.save(update_fields=['is_enabled'])
    cache.clear()


class ProductTrendsUnitTests(ManagerAPITestCase):
    """Pure builder behaviour without HTTP."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Trend Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Trend Soap',
            sku='TREND-SOAP',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )

    def test_build_rejects_invalid_product_id(self):
        with self.assertRaises(ValueError):
            build_product_trends(product_id=0)
        with self.assertRaises(ValueError):
            build_product_trends(product_id='x')

    def test_build_clamps_months_and_zero_fills(self):
        payload = build_product_trends(
            product_id=self.product.id,
            months=99,
            today=date(2026, 6, 15),
        )
        self.assertEqual(payload['months_requested'], 24)
        self.assertEqual(len(payload['months']), 24)
        self.assertEqual(payload['months'][0]['month'], '2024-07')
        self.assertEqual(payload['months'][-1]['month'], '2026-06')
        self.assertEqual(payload['summary']['quantity_sold'], 0)

    def test_build_aggregates_sold_and_received(self):
        sale = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('200.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('200.00'),
            amount_paid=Decimal('200.00'),
            cashier=self.manager_user,
            client_channel='pos',
            occurred_at=timezone.make_aware(datetime(2026, 5, 10, 12, 0, 0)),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=2,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('200.00'),
        )
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type='purchase',
            quantity=8,
            unit_cost=Decimal('40.00'),
            total_cost=Decimal('320.00'),
            user=self.manager_user,
        )
        StockMovement.objects.filter(pk=movement.pk).update(
            created_at=timezone.make_aware(datetime(2026, 5, 8, 9, 0, 0)),
        )
        payload = build_product_trends(
            product_id=self.product.id,
            months=3,
            today=date(2026, 5, 20),
        )
        may = next(row for row in payload['months'] if row['month'] == '2026-05')
        self.assertEqual(may['quantity_sold'], 2)
        self.assertEqual(may['order_count'], 1)
        self.assertEqual(may['quantity_received'], 8)
        self.assertEqual(may['revenue'], '200.00')
        self.assertEqual(payload['summary']['quantity_sold'], 2)
        self.assertEqual(payload['summary']['best_month'], '2026-05')
        self.assertTrue(
            any(ch['channel'] == 'pos' and ch['quantity'] == 2 for ch in payload['channels'])
        )


class ProductTrendsAPITests(ManagerAPITestCase):
    """HTTP integration for product-trends endpoint."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='API Trend Cat', is_active=True)
        cls.product = Product.objects.create(
            name='API Trend Tea',
            sku='TREND-TEA',
            category=cat,
            price=Decimal('50.00'),
            cost=Decimal('20.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        sale = Sale.objects.create(
            status='completed',
            payment_method='cash',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            cashier=cls.manager_user,
            client_channel='mobile',
        )
        SaleItem.objects.create(
            sale=sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('50.00'),
            subtotal=Decimal('100.00'),
        )

    def setUp(self):
        super().setUp()
        _seed_product_report_settings(product_reports=True)
        _set_product_trends_feature(True)

    def test_product_trends_requires_product_id(self):
        response = self.client.get('/api/reports/product-trends/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_trends_not_found(self):
        response = self.client.get(
            '/api/reports/product-trends/',
            {'product_id': 999999},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_product_trends_happy_path(self):
        response = self.client.get(
            '/api/reports/product-trends/',
            {'product_id': self.product.id, 'months': 6},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['product_id'], self.product.id)
        self.assertEqual(response.data['name'], 'API Trend Tea')
        self.assertEqual(response.data['months_requested'], 6)
        self.assertEqual(len(response.data['months']), 6)
        self.assertGreaterEqual(response.data['summary']['quantity_sold'], 2)
        self.assertIn('channels', response.data)

    def test_corrected_functionality_click_product_shows_month_series(self):
        """Opening a product returns month labels and sold/received keys for charts."""
        response = self.client.get(
            '/api/reports/product-trends/',
            {'product_id': self.product.id, 'months': 12},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        months = response.data['months']
        self.assertEqual(len(months), 12)
        for row in months:
            self.assertIn('label', row)
            self.assertIn('quantity_sold', row)
            self.assertIn('quantity_received', row)
            self.assertIn('revenue', row)
            self.assertIn('order_count', row)


class ProductTrendsModuleTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.product = Product.objects.create(
            name='Module Trend',
            sku='TREND-MOD',
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _seed_product_report_settings(product_reports=True)
        _set_product_trends_feature(True)

    def test_forbidden_when_product_reports_disabled(self):
        SettingsService.set('reports', 'enable_product_reports', False)
        response = self.client.get(
            '/api/reports/product-trends/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_forbidden_when_feature_disabled(self):
        _set_product_trends_feature(False)
        self.assertFalse(product_trends_feature_enabled())
        self.assertFalse(product_trends_allowed())
        response = self.client.get(
            '/api/reports/product-trends/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_allowed_when_feature_and_setting_on(self):
        self.assertTrue(product_trends_allowed())
        response = self.client.get(
            '/api/reports/product-trends/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ProductTrendsSecurityTests(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.product = Product.objects.create(
            name='Sec Trend',
            sku='TREND-SEC',
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _seed_product_report_settings(product_reports=True)
        _set_product_trends_feature(True)

    def test_unauthenticated_denied(self):
        anon = APIClient()
        response = anon.get(
            '/api/reports/product-trends/',
            {'product_id': self.product.id},
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_sales_without_reports_view_denied(self):
        response = self.client.get(
            '/api/reports/product-trends/',
            {'product_id': self.product.id},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_post_denied(self):
        response = self.client.post(
            '/api/reports/product-trends/',
            {'product_id': self.product.id},
        )
        self.assertIn(
            response.status_code,
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            ),
        )


class ProductTrendsManagerSecurityTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.product = Product.objects.create(
            name='Mgr Sec Trend',
            sku='TREND-MGR-SEC',
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _seed_product_report_settings(product_reports=True)
        _set_product_trends_feature(True)

    def test_post_rejected_for_manager(self):
        response = self.client.post(
            '/api/reports/product-trends/',
            {'product_id': self.product.id},
        )
        self.assertIn(
            response.status_code,
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            ),
        )

    def test_error_body_does_not_leak_internal_detail(self):
        response = self.client.get('/api/reports/product-trends/', {'product_id': 'abc'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = str(response.data)
        self.assertNotIn('Traceback', body)
        self.assertNotIn('password', body.lower())


class ProductTrendsStressTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.product = Product.objects.create(
            name='Stress Trend',
            sku='TREND-STRESS',
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _seed_product_report_settings(product_reports=True)
        _set_product_trends_feature(True)

    def test_build_product_trends_repeated(self):
        for _ in range(200):
            payload = build_product_trends(
                product_id=self.product.id,
                months=12,
                today=date(2026, 11, 1),
            )
            self.assertEqual(len(payload['months']), 12)

    def test_rapid_api_reads(self):
        url = '/api/reports/product-trends/'
        for _ in range(80):
            response = self.client.get(
                url,
                {'product_id': self.product.id, 'months': 6},
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data['months']), 6)
