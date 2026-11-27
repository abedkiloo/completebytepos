"""Drive sales/customer gated settings helpers to full coverage."""

from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from sales.customer_module_settings import (
    apply_customer_representation_flags,
    apply_customer_write_flags,
    customers_allow_quick_add_at_pos,
    customers_collection_payer_details_enabled,
    customers_enable_create,
    customers_enable_delete,
    customers_enable_edit,
    customers_enable_wallet_payment,
    customers_location_filters_enabled,
    customers_show_customer_code,
    customers_show_customer_type,
    customers_show_notes,
    customers_show_outstanding_balance,
    customers_show_status,
    customers_show_tax_id,
    customers_show_wallet_balance,
    customers_transfer_customer_on_collection_enabled,
    validate_customer_write,
)
from sales.module_settings import (
    apply_sale_module_settings,
    sales_allow_excess_to_wallet,
    sales_allow_partial_payment,
    sales_history_export_enabled,
    sales_late_sale_sms_enabled,
    sales_payments_trail_export_enabled,
    sales_require_customer,
    sales_show_delivery,
    sales_show_discount,
    sales_show_tax,
    sales_sms_include_payment_ref,
    sales_sms_sale_number_prefix,
    sales_sms_short_sale_number,
    sales_sms_show_balance_when_zero,
    sales_transfer_sale_customer_enabled,
    sales_transfer_sale_staff_enabled,
    sales_validate_stock_before_sale,
)
from settings.models import ModuleFeature, ModuleSetting, ModuleSettings
from settings.settings_service import SettingsService


def _set_flag(module: str, key: str, value: bool) -> None:
    cache.clear()
    ModuleSetting.objects.update_or_create(
        module=module,
        key=key,
        defaults={
            'label': key,
            'description': '',
            'default_value': value,
            'value': value,
        },
    )


def _set_feature(module_name: str, feature_key: str, enabled: bool) -> None:
    cache.clear()
    module, _ = ModuleSettings.objects.get_or_create(
        module_name=module_name,
        defaults={'is_enabled': True},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feat, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key=feature_key,
        defaults={'feature_name': feature_key, 'is_enabled': enabled},
    )
    feat.is_enabled = enabled
    feat.save(update_fields=['is_enabled'])


class SalesModuleSettingsCoverageTests(TestCase):
    def test_helpers_and_apply_zero_paths(self):
        for key, default in (
            ('show_discount', True),
            ('show_tax', True),
            ('show_delivery', True),
            ('require_customer', False),
            ('allow_partial_payment', True),
            ('allow_excess_to_wallet', True),
            ('validate_stock_before_sale', True),
            ('sms_short_sale_number', True),
            ('sms_include_payment_ref', True),
            ('sms_show_balance_when_zero', False),
        ):
            _set_flag('sales', key, default)

        self.assertTrue(sales_show_discount())
        self.assertTrue(sales_show_tax())
        self.assertTrue(sales_show_delivery())
        self.assertFalse(sales_require_customer())
        self.assertTrue(sales_allow_partial_payment())
        self.assertTrue(sales_allow_excess_to_wallet())
        self.assertTrue(sales_validate_stock_before_sale())
        self.assertTrue(sales_sms_short_sale_number())
        self.assertTrue(sales_sms_include_payment_ref())
        self.assertFalse(sales_sms_show_balance_when_zero())

        _set_feature('sales', 'history_export', False)
        self.assertFalse(sales_history_export_enabled())
        _set_feature('sales', 'payments_trail_export', False)
        self.assertFalse(sales_payments_trail_export_enabled())
        _set_feature('sales', 'transfer_sale_staff', False)
        self.assertFalse(sales_transfer_sale_staff_enabled())
        _set_feature('sales', 'transfer_sale_customer', False)
        self.assertFalse(sales_transfer_sale_customer_enabled())
        _set_feature('sales', 'late_sale_sms', False)
        self.assertFalse(sales_late_sale_sms_enabled())

        with patch(
            'sales.module_settings.SettingsService.get',
            return_value=None,
        ):
            self.assertEqual(sales_sms_sale_number_prefix(), 'S-')
        SettingsService.set('sales', 'sms_sale_number_prefix', '  ')
        self.assertEqual(sales_sms_sale_number_prefix(), 'S-')
        SettingsService.set('sales', 'sms_sale_number_prefix', 'INV-')
        self.assertEqual(sales_sms_sale_number_prefix(), 'INV-')

        # Zero amounts while flags are on → kept; flags off with zero → stripped.
        cleaned = apply_sale_module_settings(
            {
                'discount_amount': Decimal('0'),
                'tax_amount': Decimal('0'),
                'delivery_cost': Decimal('0'),
                'allow_partial_payment': False,
                'excess_payment_choice': 'change',
            }
        )
        self.assertEqual(cleaned['discount_amount'], Decimal('0'))

        _set_flag('sales', 'show_discount', False)
        _set_flag('sales', 'show_tax', False)
        _set_flag('sales', 'show_delivery', False)
        stripped = apply_sale_module_settings(
            {
                'discount_amount': Decimal('0'),
                'tax_amount': Decimal('0'),
                'delivery_cost': Decimal('0'),
                'delivery_method': 'courier',
                'shipping_address': 'Somewhere',
            }
        )
        self.assertEqual(stripped['discount_amount'], Decimal('0'))
        self.assertEqual(stripped['tax_amount'], Decimal('0'))
        self.assertEqual(stripped['delivery_cost'], Decimal('0'))
        self.assertEqual(stripped['delivery_method'], 'pickup')
        self.assertIsNone(stripped['shipping_address'])


class CustomerModuleSettingsCoverageTests(TestCase):
    def test_flags_representation_and_write(self):
        for key in (
            'show_customer_code',
            'show_outstanding_balance',
            'show_wallet_balance',
            'enable_customer_create',
            'enable_customer_edit',
            'enable_customer_delete',
            'show_customer_type',
            'show_tax_id',
            'show_customer_notes',
            'show_customer_status',
            'allow_quick_add_at_pos',
            'enable_wallet_payment',
        ):
            _set_flag('customers', key, True)

        self.assertTrue(customers_show_customer_code())
        self.assertTrue(customers_show_outstanding_balance())
        self.assertTrue(customers_show_wallet_balance())
        self.assertTrue(customers_enable_create())
        self.assertTrue(customers_enable_edit())
        self.assertTrue(customers_enable_delete())
        self.assertTrue(customers_show_customer_type())
        self.assertTrue(customers_show_tax_id())
        self.assertTrue(customers_show_notes())
        self.assertTrue(customers_show_status())
        self.assertTrue(customers_allow_quick_add_at_pos())
        self.assertTrue(customers_enable_wallet_payment())

        _set_feature('customers', 'location_filters', False)
        self.assertFalse(customers_location_filters_enabled())
        _set_feature('customers', 'transfer_customer_on_collection', False)
        self.assertFalse(customers_transfer_customer_on_collection_enabled())
        _set_feature('customers', 'collection_payer_details', False)
        self.assertFalse(customers_collection_payer_details_enabled())

        for key in (
            'show_customer_code',
            'show_outstanding_balance',
            'show_wallet_balance',
            'show_customer_type',
            'show_tax_id',
            'show_customer_notes',
            'show_customer_status',
        ):
            _set_flag('customers', key, False)

        data = apply_customer_representation_flags(
            {
                'customer_code': 'C1',
                'total_outstanding': 10,
                'total_invoices': 1,
                'wallet_balance': 2,
                'customer_type': 'business',
                'is_active': True,
                'tax_id': 'T',
                'notes': 'n',
                'name': 'Ada',
            }
        )
        self.assertEqual(data, {'name': 'Ada'})

        attrs = validate_customer_write(
            {
                'customer_type': 'business',
                'tax_id': 'X',
                'notes': 'y',
                'is_active': False,
                'name': 'Bo',
            }
        )
        self.assertEqual(attrs['customer_type'], 'individual')
        self.assertNotIn('tax_id', attrs)
        self.assertNotIn('notes', attrs)
        self.assertNotIn('is_active', attrs)
        self.assertEqual(attrs['name'], 'Bo')

        write_only = apply_customer_write_flags({'customer_type': 'business', 'name': 'Cy'})
        self.assertNotIn('customer_type', write_only)
