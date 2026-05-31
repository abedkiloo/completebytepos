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
