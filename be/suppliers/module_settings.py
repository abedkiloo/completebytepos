"""Suppliers module flags via SettingsService."""

from settings.settings_service import SettingsService

MODULE = 'suppliers'


def _enabled(key: str, default: bool = True) -> bool:
    return bool(SettingsService.get(MODULE, key, default=default))


def suppliers_show_supplier_code() -> bool:
    return _enabled('show_supplier_code', True)


def suppliers_show_supplier_type() -> bool:
    return _enabled('show_supplier_type', True)


def suppliers_show_contact_details() -> bool:
    return _enabled('show_contact_details', True)


def suppliers_show_business_details() -> bool:
    return _enabled('show_business_details', True)


def suppliers_show_payment_terms() -> bool:
    return _enabled('show_payment_terms', True)


def suppliers_show_credit_fields() -> bool:
    return _enabled('show_credit_fields', True)


def suppliers_show_rating() -> bool:
    return _enabled('show_supplier_rating', True)


def suppliers_show_preferred_flag() -> bool:
    return _enabled('show_preferred_flag', True)


def suppliers_show_notes() -> bool:
    return _enabled('show_supplier_notes', True)


def suppliers_show_status() -> bool:
    from settings.store_settings_helpers import entity_status_visible

    return entity_status_visible(_enabled('show_supplier_status', True))


def suppliers_enable_create() -> bool:
    return _enabled('enable_supplier_create', True)


def suppliers_enable_edit() -> bool:
    return _enabled('enable_supplier_edit', True)


def suppliers_enable_delete() -> bool:
    return _enabled('enable_supplier_delete', True)


def suppliers_enable_statistics() -> bool:
    return _enabled('enable_supplier_statistics', True)


def suppliers_enable_products() -> bool:
    return _enabled('enable_supplier_products', True)


def apply_supplier_representation_flags(data: dict) -> dict:
    if not suppliers_show_supplier_code():
        data.pop('supplier_code', None)
    if not suppliers_show_supplier_type():
        data.pop('supplier_type', None)
    if not suppliers_show_contact_details():
        data.pop('contact_person', None)
        data.pop('email', None)
        data.pop('phone', None)
        data.pop('alternate_phone', None)
        data.pop('address', None)
        data.pop('city', None)
        data.pop('state', None)
        data.pop('country', None)
        data.pop('postal_code', None)
        data.pop('full_address', None)
        data.pop('primary_contact', None)
    if not suppliers_show_business_details():
        data.pop('tax_id', None)
        data.pop('registration_number', None)
        data.pop('website', None)
    if not suppliers_show_payment_terms():
        data.pop('payment_terms', None)
    if not suppliers_show_credit_fields():
        data.pop('credit_limit', None)
        data.pop('account_balance', None)
        data.pop('is_credit_available', None)
    if not suppliers_show_rating():
        data.pop('rating', None)
    if not suppliers_show_preferred_flag():
        data.pop('is_preferred', None)
    if not suppliers_show_notes():
        data.pop('notes', None)
    if not suppliers_show_status():
        data.pop('is_active', None)
    return data


def validate_supplier_write(attrs: dict) -> dict:
    attrs = dict(attrs)
    if not suppliers_show_supplier_type():
        attrs.pop('supplier_type', None)
    if not suppliers_show_contact_details():
        for key in (
            'contact_person', 'email', 'phone', 'alternate_phone',
            'address', 'city', 'state', 'country', 'postal_code',
        ):
            attrs.pop(key, None)
    if not suppliers_show_business_details():
        attrs.pop('tax_id', None)
        attrs.pop('registration_number', None)
        attrs.pop('website', None)
    if not suppliers_show_payment_terms():
        attrs.pop('payment_terms', None)
    if not suppliers_show_credit_fields():
        attrs.pop('credit_limit', None)
        attrs.pop('account_balance', None)
    if not suppliers_show_rating():
        attrs.pop('rating', None)
    if not suppliers_show_preferred_flag():
        attrs.pop('is_preferred', None)
    if not suppliers_show_notes():
        attrs.pop('notes', None)
    if not suppliers_show_status():
        attrs.pop('is_active', None)
    if not suppliers_show_supplier_type() and 'supplier_type' not in attrs:
        attrs['supplier_type'] = 'business'
    if not suppliers_show_payment_terms() and 'payment_terms' not in attrs:
        attrs['payment_terms'] = 'net_30'
    return attrs
