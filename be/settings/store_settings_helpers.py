"""Helpers for tenant-wide store / POS configuration."""

DEFAULT_STORE_NAME = 'Omuwenga Suppliers'
STORE_NAME_MAX_LENGTH = 120

DEFAULT_PAYMENT_METHODS = ['cash', 'mpesa', 'wallet']

VALID_PAYMENT_METHODS = frozenset(DEFAULT_PAYMENT_METHODS)

COLLECTION_PAYMENT_METHODS = ('cash', 'mpesa')
COLLECTION_PAYMENT_CHOICES = (
    ('cash', 'Cash'),
    ('mpesa', 'M-PESA'),
)


def normalize_store_name(value):
    text = str(value or '').strip()
    if not text:
        return DEFAULT_STORE_NAME
    return text[:STORE_NAME_MAX_LENGTH]


def resolved_store_name():
    from settings.models import StoreSettings

    return normalize_store_name(StoreSettings.load().store_name)


def user_may_edit_pricing(user):
    """Managers and super admins may set product prices (see sensitive_edits)."""
    from accounts.sensitive_edits import user_may_edit_financial_fields

    return user_may_edit_financial_fields(user)


def normalize_payment_methods(methods):
    if not methods:
        return list(DEFAULT_PAYMENT_METHODS)
    cleaned = []
    for m in methods:
        key = str(m).strip().lower()
        if key in VALID_PAYMENT_METHODS and key not in cleaned:
            cleaned.append(key)
    return cleaned or list(DEFAULT_PAYMENT_METHODS)


def entity_status_ui_hidden() -> bool:
    """When True, all per-module active/inactive UI and API fields are suppressed."""
    from settings.models import StoreSettings

    return bool(StoreSettings.load().hide_entity_status_toggles)


def entity_status_visible(module_flag_enabled: bool) -> bool:
    """Combine a module status flag with the store-wide status UI kill switch."""
    if entity_status_ui_hidden():
        return False
    return bool(module_flag_enabled)
