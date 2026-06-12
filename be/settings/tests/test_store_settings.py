"""Tests for store-wide settings (receipt, payments, catalog rules)."""

import json

from decimal import Decimal

from django.contrib.auth.models import User
from django.http import QueryDict
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from approvals.models import PendingChange
from products.models import Category, Product
from settings.models import StoreSettings
from settings.serializers import StoreSettingsSerializer
from settings.store_settings_helpers import (
    DEFAULT_PAYMENT_METHODS,
    normalize_payment_methods,
    user_may_edit_pricing,
)
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import (
    ManagerAPITestCase,
    SalesAPITestCase,
    SuperAdminAPITestCase,
)


class StoreSettingsHelperTests(TestCase):
    def test_normalize_payment_methods_defaults_when_empty(self):
        self.assertEqual(normalize_payment_methods([]), list(DEFAULT_PAYMENT_METHODS))
        self.assertEqual(normalize_payment_methods(None), list(DEFAULT_PAYMENT_METHODS))

    def test_normalize_payment_methods_deduplicates_and_lowercases(self):
        result = normalize_payment_methods(['CASH', 'mpesa', 'cash', 'card'])
        self.assertEqual(result, ['cash', 'mpesa', 'card'])

    def test_normalize_payment_methods_ignores_invalid(self):
        result = normalize_payment_methods(['cash', 'bitcoin'])
        self.assertEqual(result, ['cash'])

    def test_user_may_edit_pricing_superuser(self):
        user = User.objects.create_superuser('admin', 'a@t.com', 'pass')
        self.assertTrue(user_may_edit_pricing(user))

    def test_user_may_edit_pricing_anonymous(self):
        self.assertFalse(user_may_edit_pricing(None))


class StoreSettingsModelTests(TestCase):
    def test_load_is_singleton(self):
        first = StoreSettings.load()
        second = StoreSettings.load()
        self.assertEqual(first.pk, 1)
        self.assertEqual(second.pk, 1)
        self.assertEqual(StoreSettings.objects.count(), 1)
        self.assertEqual(first.enabled_payment_methods, list(DEFAULT_PAYMENT_METHODS))

    def test_maker_checker_enabled_by_default(self):
        store = StoreSettings.load()
        self.assertTrue(store.maker_checker_enabled)


class StoreSettingsSerializerTests(TestCase):
    def setUp(self):
        self.instance = StoreSettings.load()
        self.factory = APIRequestFactory()

    def _serializer(self, data, partial=True):
        request = self.factory.patch('/api/settings/store-settings/')
        return StoreSettingsSerializer(
            self.instance,
            data=data,
            partial=partial,
            context={'request': request},
        )

    def test_accepts_json_array_in_plain_dict(self):
        ser = self._serializer({'enabled_payment_methods': ['cash', 'mpesa']})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data['enabled_payment_methods'], ['cash', 'mpesa'])

    def test_parses_json_string_from_multipart_style_querydict(self):
        qd = QueryDict(mutable=True)
        qd['enabled_payment_methods'] = json.dumps(['cash', 'wallet', 'card'])
        qd['allow_sales_add_products'] = 'true'
        qd['receipt_footer_text'] = 'Karibu tena'

        ser = self._serializer(qd)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(
            ser.validated_data['enabled_payment_methods'],
            ['cash', 'wallet', 'card'],
        )

    def test_rejects_unknown_payment_method(self):
        ser = self._serializer({'enabled_payment_methods': ['cash', 'crypto']})
        self.assertFalse(ser.is_valid())
        self.assertIn('enabled_payment_methods', ser.errors)

    def test_rejects_empty_payment_methods_list(self):
        ser = self._serializer({'enabled_payment_methods': []})
        self.assertFalse(ser.is_valid())
        self.assertIn('enabled_payment_methods', ser.errors)


class StoreSettingsAPITests(SuperAdminAPITestCase):
    url = '/api/settings/store-settings/'

    def setUp(self):
        super().setUp()
        disable_maker_checker()

    def test_get_requires_authentication(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_returns_defaults_for_authenticated_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('enabled_payment_methods', response.data)
        self.assertEqual(
            response.data['enabled_payment_methods'],
            list(DEFAULT_PAYMENT_METHODS),
        )

    def test_super_admin_patch_json(self):
        payload = {
            'allow_sales_add_products': True,
            'sales_catalog_skip_pricing': True,
            'hide_entity_status_toggles': True,
            'enabled_payment_methods': ['cash', 'mpesa'],
            'receipt_header_text': 'Welcome',
            'receipt_footer_text': 'Asante sana',
            'receipt_show_logo': False,
            'receipt_auto_print': False,
        }
        response = self.client.patch(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['allow_sales_add_products'])
        self.assertEqual(response.data['enabled_payment_methods'], ['cash', 'mpesa'])
        self.assertEqual(response.data['receipt_footer_text'], 'Asante sana')

        stored = StoreSettings.load()
        self.assertTrue(stored.allow_sales_add_products)
        self.assertEqual(stored.enabled_payment_methods, ['cash', 'mpesa'])

    def test_super_admin_patch_multipart_with_json_string_payment_methods(self):
        """Regression: multipart must not fail with 'Value must be valid JSON.'"""
        response = self.client.patch(
            self.url,
            {
                'allow_sales_add_products': 'true',
                'sales_catalog_skip_pricing': 'true',
                'hide_entity_status_toggles': 'false',
                'enabled_payment_methods': json.dumps(['cash', 'card']),
                'receipt_footer_text': 'Thank you',
                'receipt_show_logo': 'true',
                'receipt_auto_print': 'false',
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['enabled_payment_methods'], ['cash', 'card'])

    def test_clear_receipt_logo_flag(self):
        response = self.client.patch(
            self.url,
            {'clear_receipt_logo': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_super_admin_can_toggle_maker_checker(self):
        response = self.client.patch(
            self.url,
            {'maker_checker_enabled': True, 'emergency_stock_mode': False},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['maker_checker_enabled'])
        self.assertFalse(response.data['emergency_stock_mode'])

        stored = StoreSettings.load()
        self.assertTrue(stored.maker_checker_enabled)

        off = self.client.patch(
            self.url,
            {'maker_checker_enabled': False},
            format='json',
        )
        self.assertEqual(off.status_code, status.HTTP_200_OK)
        stored.refresh_from_db()
        self.assertFalse(stored.maker_checker_enabled)


class StoreSettingsMakerCheckerToggleTests(ManagerAPITestCase):
    """F1: disabling maker-checker lets sensitive writes apply immediately."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Toggle Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Toggle Product',
            sku='MC-TOG-1',
            category=cat,
            price=Decimal('40'),
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.emergency_stock_mode = False
        store.save(update_fields=['maker_checker_enabled', 'emergency_stock_mode'])
        PendingChange.objects.all().delete()

    def test_price_patch_applies_immediately_when_maker_checker_disabled(self):
        resp = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '55.00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('55'))


class StoreSettingsAPIPermissionTests(ManagerAPITestCase):
    url = '/api/settings/store-settings/'

    def test_manager_can_read(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_cannot_patch(self):
        response = self.client.patch(
            self.url,
            {'enabled_payment_methods': ['cash']},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class StoreSettingsSalesReadTests(SalesAPITestCase):
    url = '/api/settings/store-settings/'

    def test_sales_can_read_for_pos(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('enabled_payment_methods', response.data)

    def test_sales_cannot_patch(self):
        response = self.client.patch(
            self.url,
            {'enabled_payment_methods': ['cash']},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
