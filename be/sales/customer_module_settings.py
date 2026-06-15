"""Customers module flags via SettingsService."""

from settings.settings_service import SettingsService

MODULE = 'customers'


def _enabled(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get(MODULE, key, default=default))


def customers_show_customer_code() -> bool:
    return _enabled('show_customer_code', True)


def customers_show_outstanding_balance() -> bool:
    return _enabled('show_outstanding_balance', True)


def customers_show_wallet_balance() -> bool:
    return _enabled('show_wallet_balance', True)


def customers_enable_create() -> bool:
    return _enabled('enable_customer_create', True)


def customers_enable_edit() -> bool:
    return _enabled('enable_customer_edit', True)


def customers_enable_delete() -> bool:
    return _enabled('enable_customer_delete', True)


def customers_show_customer_type() -> bool:
    return _enabled('show_customer_type', True)


def customers_show_tax_id() -> bool:
    return _enabled('show_tax_id', True)


def customers_show_notes() -> bool:
    return _enabled('show_customer_notes', True)


def customers_show_status() -> bool:
    from settings.store_settings_helpers import entity_status_visible

    return entity_status_visible(_enabled('show_customer_status', True))


def customers_allow_quick_add_at_pos() -> bool:
    return _enabled('allow_quick_add_at_pos', True)


def customers_enable_wallet_payment() -> bool:
    return _enabled('enable_wallet_payment', True)


def apply_customer_representation_flags(data: dict) -> dict:
    if not customers_show_customer_code():
        data.pop('customer_code', None)
    if not customers_show_outstanding_balance():
        data.pop('total_outstanding', None)
        data.pop('total_invoices', None)
    if not customers_show_wallet_balance():
        data.pop('wallet_balance', None)
    if not customers_show_customer_type():
        data.pop('customer_type', None)
    if not customers_show_status():
        data.pop('is_active', None)
    if not customers_show_tax_id():
        data.pop('tax_id', None)
    if not customers_show_notes():
        data.pop('notes', None)
    return data


def apply_customer_write_flags(attrs: dict) -> dict:
    attrs = dict(attrs)
    if not customers_show_customer_type():
        attrs.pop('customer_type', None)
    if not customers_show_tax_id():
        attrs.pop('tax_id', None)
    if not customers_show_notes():
        attrs.pop('notes', None)
    if not customers_show_status():
        attrs.pop('is_active', None)
    return attrs


def validate_customer_write(attrs: dict) -> dict:
    attrs = apply_customer_write_flags(attrs)
    if not customers_show_customer_type():
        attrs['customer_type'] = 'individual'
    return attrs
