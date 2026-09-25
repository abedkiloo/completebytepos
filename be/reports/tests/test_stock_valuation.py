"""Current stock valuation report."""

from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework import status

from products.models import Category, Color, Product, ProductVariant, Size
from reports.stock_valuation import (
    StockValuationReportService,
    _line,
    _qty,
    _truthy,
    _variant_label,
)
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class StockValuationHelperTests(SimpleTestCase):
    def test_qty_and_flags(self):
        self.assertEqual(_qty(None), 0)
        self.assertEqual(_qty('nope'), 0)
        self.assertEqual(_qty(-4), 0)
        self.assertEqual(_qty('3'), 3)
        self.assertTrue(_truthy('yes'))
        self.assertTrue(_truthy('ON'))
        self.assertFalse(_truthy(''))

    def test_line_and_variant_label(self):
        row = _line(
            sku='A',
            product_name='Table',
            variant='',
            category='Sofas',
            quantity=2,
            unit_cost=Decimal('10.00'),
            unit_price=Decimal('25.00'),
        )
        self.assertEqual(row['cost_value'], 20.0)
        self.assertEqual(row['retail_value'], 50.0)
        variant = type('V', (), {'size_id': None, 'color_id': None, 'size': None, 'color': None})()
        self.assertEqual(_variant_label(variant), '')
        sized = type(
            'V',
            (),
            {
                'size_id': 1,
                'color_id': 2,
                'size': type('S', (), {'name': 'Large'})(),
                'color': type('C', (), {'name': 'Grey'})(),
            },
        )()
        self.assertEqual(_variant_label(sized), 'Large / Grey')



class StockValuationReportTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Sofas', is_active=True)
        cls.simple = Product.objects.create(
            name='Coffee table',
            sku='TBL-1',
            category=cat,
            price=Decimal('8000.00'),
            cost=Decimal('4000.00'),
            stock_quantity=3,
            track_stock=True,
            is_active=True,
        )
        cls.empty = Product.objects.create(
            name='Empty stool',
            sku='STL-0',
            category=cat,
            price=Decimal('1500.00'),
            cost=Decimal('700.00'),
            stock_quantity=0,
            track_stock=True,
            is_active=True,
        )
        Product.objects.create(
            name='Variant shell',
            sku='SHELL-1',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=6,
            has_variants=True,
            track_stock=True,
            is_active=True,
        )
        cls.sofa = Product.objects.create(
            name='L-shape sofa',
            sku='SOFA-1',
            category=cat,
            price=Decimal('50000.00'),
            cost=Decimal('30000.00'),
            stock_quantity=4,
            has_variants=True,
            track_stock=True,
            is_active=True,
        )
        size = Size.objects.create(name='Large', code='L')
        colour = Color.objects.create(name='Grey')
        ProductVariant.objects.create(
            product=cls.sofa,
            size=size,
            color=colour,
            sku='SOFA-1-LG',
            price=Decimal('52000.00'),
            cost=Decimal('31000.00'),
            stock_quantity=2,
            is_active=True,
        )
        ProductVariant.objects.create(
            product=cls.sofa,
            size=size,
            color=None,
            sku='SOFA-1-L',
            stock_quantity=1,
            is_active=True,
        )
        ProductVariant.objects.create(
            product=cls.sofa,
            size=None,
            color=colour,
            sku='SOFA-1-GREY',
            stock_quantity=0,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        from django.core.cache import cache

        cache.clear()
        SettingsService.set('reports', 'show_cost_and_profit', True)
        SettingsService.set('reports', 'enable_inventory_reports', True)

    def test_json_lists_on_hand_stock_with_owner_and_values(self):
        response = self.client.get('/api/reports/stock_valuation/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['owner'], 'Omuwenga Suppliers')
        skus = {row['sku']: row for row in response.data['lines']}
        self.assertIn('TBL-1', skus)
        self.assertEqual(skus['TBL-1']['quantity'], 3)
        self.assertEqual(skus['TBL-1']['cost_value'], 12000.0)
        self.assertEqual(skus['TBL-1']['retail_value'], 24000.0)
        self.assertNotIn('STL-0', skus)
        self.assertIn('SOFA-1-LG', skus)
        self.assertEqual(skus['SOFA-1-LG']['variant'], 'Large / Grey')
        self.assertEqual(skus['SOFA-1-LG']['quantity'], 2)
        self.assertNotIn('SOFA-1', skus)
        self.assertIn('SHELL-1', skus)
        self.assertEqual(skus['SHELL-1']['quantity'], 6)
        self.assertEqual(response.data['summary']['zero_stock_skus'], 2)

    def test_include_zero_adds_empty_skus(self):
        response = self.client.get('/api/reports/stock_valuation/', {'include_zero': '1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        skus = {row['sku'] for row in response.data['lines']}
        self.assertIn('STL-0', skus)
        self.assertIn('SOFA-1-GREY', skus)

    def test_build_without_request_uses_defaults(self):
        payload = StockValuationReportService.build()
        self.assertEqual(payload['owner'], 'Omuwenga Suppliers')
        self.assertFalse(payload['include_zero'])

    def test_include_zero_from_get_fallback(self):
        class FakeRequest:
            query_params = {}
            GET = {'include_zero': 'true'}

        payload = StockValuationReportService.build(FakeRequest())
        self.assertTrue(payload['include_zero'])

    def test_pdf_and_xlsx_are_branded(self):
        pdf = self.client.get('/api/reports/stock_valuation/', {'format': 'pdf'})
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        xlsx = self.client.get('/api/reports/stock_valuation/', {'format': 'xlsx'})
        self.assertEqual(xlsx.status_code, status.HTTP_200_OK)
        self.assertGreater(len(xlsx.content), 100)
        csv_body = self.client.get('/api/reports/stock_valuation/', {'format': 'csv'})
        self.assertEqual(csv_body.status_code, status.HTTP_200_OK)
        text = csv_body.content.decode('utf-8-sig')
        self.assertTrue(text.startswith('Omuwenga Suppliers'))
        self.assertIn('Coffee table', text)

    def test_cost_hidden_strips_cost_columns(self):
        from django.core.cache import cache

        cache.clear()
        ModuleSetting.objects.update_or_create(
            module='reports',
            key='show_cost_and_profit',
            defaults={
                'label': 'show_cost_and_profit',
                'description': '',
                'default_value': True,
                'value': False,
            },
        )
        SettingsService.set('reports', 'show_cost_and_profit', False)
        response = self.client.get('/api/reports/stock_valuation/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('cost_value', response.data.get('summary', {}))
        self.assertTrue(response.data['lines'])
        self.assertNotIn('unit_cost', response.data['lines'][0])
        self.assertIn('retail_value', response.data['lines'][0])


class StockValuationAccessTests(SalesAPITestCase):
    def test_sales_staff_cannot_open_stock_valuation(self):
        response = self.client.get('/api/reports/stock_valuation/')
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED),
        )
