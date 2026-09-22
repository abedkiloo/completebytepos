"""Sale origin: web vs mobile app."""

from decimal import Decimal

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from rest_framework import status

from products.models import Category, Product
from sales.client_channel import resolve_client_channel
from sales.models import Sale
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


class ResolveClientChannelTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_payload_wins_over_header_and_ua(self):
        request = self.factory.post(
            '/',
            HTTP_X_CLIENT_CHANNEL='web',
            HTTP_USER_AGENT='Dart/3.5 (dart:io)',
        )
        self.assertEqual(
            resolve_client_channel(request, {'client_channel': 'mobile'}),
            'mobile',
        )

    def test_header_when_body_omitted(self):
        request = self.factory.post('/', HTTP_X_CLIENT_CHANNEL='web')
        self.assertEqual(resolve_client_channel(request, {}), 'web')

    def test_dart_user_agent_is_mobile(self):
        request = self.factory.post('/', HTTP_USER_AGENT='Dart/3.5 (dart:io)')
        self.assertEqual(resolve_client_channel(request, {}), 'mobile')

    def test_browser_user_agent_is_web(self):
        request = self.factory.post(
            '/',
            HTTP_USER_AGENT='Mozilla/5.0 Chrome/120.0.0.0',
        )
        self.assertEqual(resolve_client_channel(request, {}), 'web')

    def test_app_alias_maps_to_mobile(self):
        self.assertEqual(
            resolve_client_channel(None, {'client_channel': 'app'}),
            'mobile',
        )


class SaleClientChannelAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.tenant, self.branch, _ = self.create_tenant_with_branches(self.manager_user)
        self.set_session_branch(self.tenant, self.branch)
        category = Category.objects.create(name='Channel Cat', is_active=True)
        self.product = Product.objects.create(
            name='Channel Product',
            sku='CHN-1',
            category=category,
            price=Decimal('50.00'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        cache.clear()
        SettingsService.set('sales', 'validate_stock_before_sale', False)

    def _payload(self, **overrides):
        payload = {
            'items': [
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'unit_price': '50.00',
                }
            ],
            'payment_method': 'cash',
            'amount_paid': '50.00',
        }
        payload.update(overrides)
        return payload

    def test_create_persists_mobile_from_body(self):
        response = self.client.post(
            '/api/sales/',
            self._payload(client_channel='mobile'),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['client_channel'], 'mobile')
        sale = Sale.objects.get(pk=response.data['id'])
        self.assertEqual(sale.client_channel, 'mobile')

    def test_create_uses_header_when_body_omitted(self):
        response = self.client.post(
            '/api/sales/',
            self._payload(),
            format='json',
            HTTP_X_CLIENT_CHANNEL='web',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['client_channel'], 'web')

    def test_existing_sales_default_unknown(self):
        sale = Sale.objects.create(
            cashier=self.manager_user,
            branch=self.branch,
            status='completed',
            payment_method='cash',
            subtotal=Decimal('10.00'),
            total=Decimal('10.00'),
            amount_paid=Decimal('10.00'),
        )
        self.assertEqual(sale.client_channel, 'unknown')
