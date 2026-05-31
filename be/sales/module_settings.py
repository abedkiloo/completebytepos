"""Sales / checkout module flags via SettingsService."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from rest_framework import serializers

from settings.settings_service import SettingsService

MODULE = 'sales'


def _enabled(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get(MODULE, key, default=default))


def sales_show_discount() -> bool:
    return _enabled('show_discount', True)


def sales_show_tax() -> bool:
    return _enabled('show_tax', True)


def sales_show_delivery() -> bool:
    return _enabled('show_delivery', True)


def sales_require_customer() -> bool:
    return _enabled('require_customer', False)


def sales_allow_partial_payment() -> bool:
    return _enabled('allow_partial_payment', True)


def sales_allow_excess_to_wallet() -> bool:
    return _enabled('allow_excess_to_wallet', True)


def sales_validate_stock_before_sale() -> bool:
    return _enabled('validate_stock_before_sale', True)


def apply_sale_module_settings(attrs: dict) -> dict:
    """
    Enforce module flags on incoming sale payloads (create / checkout).
    Strips disallowed amounts and rejects forbidden combinations.
    """
    attrs = dict(attrs)

    discount = Decimal(str(attrs.get('discount_amount') or 0))
    tax = Decimal(str(attrs.get('tax_amount') or 0))
    delivery = Decimal(str(attrs.get('delivery_cost') or 0))

    if not sales_show_discount():
        if discount > 0:
            raise serializers.ValidationError(
                {'discount_amount': 'Discounts are disabled in store settings.'}
            )
        attrs['discount_amount'] = Decimal('0')

    if not sales_show_tax():
        if tax > 0:
            raise serializers.ValidationError(
                {'tax_amount': 'Tax is disabled in store settings.'}
            )
        attrs['tax_amount'] = Decimal('0')

    if not sales_show_delivery():
        if delivery > 0:
            raise serializers.ValidationError(
                {'delivery_cost': 'Delivery charges are disabled in store settings.'}
            )
        attrs['delivery_cost'] = Decimal('0')
        attrs['delivery_method'] = 'pickup'
        attrs['shipping_address'] = None

    customer_id = attrs.get('customer_id')
    if sales_require_customer() and not customer_id:
        raise serializers.ValidationError(
            {'customer_id': 'A registered customer is required for every sale.'}
        )

    allow_partial = attrs.get('allow_partial_payment', False)
    if allow_partial and not sales_allow_partial_payment():
        raise serializers.ValidationError(
            {'allow_partial_payment': 'Partial payment is disabled in store settings.'}
        )

    excess_choice = attrs.get('excess_payment_choice', 'change')
    if excess_choice == 'wallet' and not sales_allow_excess_to_wallet():
        raise serializers.ValidationError(
            {'excess_payment_choice': 'Crediting excess to wallet is disabled in store settings.'}
        )

    return attrs
