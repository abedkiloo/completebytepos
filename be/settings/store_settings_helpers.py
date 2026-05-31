"""Helpers for tenant-wide store / POS configuration."""

DEFAULT_PAYMENT_METHODS = ['cash', 'mpesa', 'wallet', 'card']

VALID_PAYMENT_METHODS = frozenset(DEFAULT_PAYMENT_METHODS)


def user_may_edit_pricing(user):
    """Managers and super admins may set product prices."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    if profile.role in ('super_admin', 'manager'):
        return True
    custom = getattr(profile, 'custom_role', None)
    if custom and custom.name in ('Super Admin', 'Manager'):
        return True
    return False


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
