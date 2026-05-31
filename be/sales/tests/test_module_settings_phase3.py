"""Phase 3 — sales / checkout module settings gates."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import serializers, status

from products.models import Category, Product
from sales.models import Customer
from sales.module_settings import apply_sale_module_settings
from sales.serializers import SaleCreateSerializer
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from utils.tests.api_test_base import ManagerAPITestCase


def _seed_sales_settings():
    cache.clear()
    for key, default in (
        ('show_discount', True),
        ('show_tax', True),
        ('show_delivery', True),
        ('require_customer', False),
        ('allow_partial_payment', True),
        ('allow_excess_to_wallet', True),
        ('validate_stock_before_sale', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='sales',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class ApplySaleModuleSettingsUnitTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_sales_settings()

    def test_rejects_discount_when_show_discount_off(self):
        SettingsService.set('sales', 'show_discount', False)
        with self.assertRaises(serializers.ValidationError) as ctx:
            apply_sale_module_settings({'discount_amount': Decimal('10')})
        self.assertIn('discount_amount', ctx.exception.detail)

    def test_rejects_tax_when_show_tax_off(self):
        SettingsService.set('sales', 'show_tax', False)
        with self.assertRaises(serializers.ValidationError):
            apply_sale_module_settings({'tax_amount': Decimal('5')})

    def test_rejects_delivery_when_show_delivery_off(self):
        SettingsService.set('sales', 'show_delivery', False)
        with self.assertRaises(serializers.ValidationError):
            apply_sale_module_settings({'delivery_cost': Decimal('50')})

    def test_requires_customer_when_flag_on(self):
        SettingsService.set('sales', 'require_customer', True)
        with self.assertRaises(serializers.ValidationError) as ctx:
            apply_sale_module_settings({'customer_id': None})
        self.assertIn('customer_id', ctx.exception.detail)

    def test_rejects_partial_payment_when_disabled(self):
        SettingsService.set('sales', 'allow_partial_payment', False)
        with self.assertRaises(serializers.ValidationError):
            apply_sale_module_settings({'allow_partial_payment': True})

    def test_rejects_wallet_excess_when_disabled(self):
        SettingsService.set('sales', 'allow_excess_to_wallet', False)
        with self.assertRaises(serializers.ValidationError):
            apply_sale_module_settings({'excess_payment_choice': 'wallet'})


class SaleCreateModuleSettingsIntegrationTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_sales_settings()
        self.tenant, self.branch, _ = self.create_tenant_with_branches(self.manager_user)
        self.set_session_branch(self.tenant, self.branch)
        self.category = Category.objects.create(name='Sales Flag Cat', is_active=True)
        self.product = Product.objects.create(
            name='Sales Flag Product',
            sku='SFL-1',
            category=self.category,
            price='100.00',
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )
        self.customer = Customer.objects.create(name='Registered Buyer', is_active=True)

    def _sale_payload(self, **overrides):
        payload = {
            'items': [
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'unit_price': '100.00',
                }
            ],
            'payment_method': 'cash',
            'amount_paid': '100.00',
            'tax_amount': '0',
            'discount_amount': '0',
            'delivery_cost': '0',
        }
        payload.update(overrides)
        return payload

    def test_create_rejects_discount_when_disabled(self):
        SettingsService.set('sales', 'show_discount', False)
        response = self.client.post(
            '/api/sales/',
            self._sale_payload(discount_amount='15.00'),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('discount_amount', response.data)

    def test_create_rejects_oversell_when_stock_validation_on(self):
        SettingsService.set('sales', 'validate_stock_before_sale', True)
        self.product.stock_quantity = 2
        self.product.save(update_fields=['stock_quantity'])
        payload = self._sale_payload()
        payload['items'][0]['quantity'] = 5
        response = self.client.post('/api/sales/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_allows_oversell_when_stock_validation_off(self):
        SettingsService.set('sales', 'validate_stock_before_sale', False)
        self.product.stock_quantity = 2
        self.product.save(update_fields=['stock_quantity'])
        payload = self._sale_payload()
        payload['items'][0]['quantity'] = 5
        payload['amount_paid'] = '500.00'
        response = self.client.post('/api/sales/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 2)

    def test_create_rejects_walk_in_when_customer_required(self):
        SettingsService.set('sales', 'require_customer', True)
        response = self.client.post('/api/sales/', self._sale_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('customer_id', response.data)

    def test_create_succeeds_with_customer_when_required(self):
        SettingsService.set('sales', 'require_customer', True)
        response = self.client.post(
            '/api/sales/',
            self._sale_payload(customer_id=self.customer.id),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_serializer_validate_applies_flags(self):
        SettingsService.set('sales', 'show_tax', False)
        ser = SaleCreateSerializer(
            data=self._sale_payload(tax_amount='12.00'),
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('tax_amount', ser.errors)
