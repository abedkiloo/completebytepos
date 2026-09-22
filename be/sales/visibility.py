"""Who may see store-wide sales vs only their own."""

from __future__ import annotations

# Roles that always see every cashier's sales (without needing sales.view_all).
_STOREWIDE_ROLE_NAMES = frozenset({
    'Super Admin',
    'Admin',
    'Administrator',
})

_STOREWIDE_LEGACY_ROLES = frozenset({
    'super_admin',
    'admin',
})


def user_sees_all_sales(user) -> bool:
    """
    Store-wide sales (today / week / month / history totals).

    Default: only Super Admin / Admin.
    Managers and sales staff see only their own sales (cashier or served_by).
    Admins can grant ``sales.view_all`` on any role for store-wide visibility.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True

    profile = getattr(user, 'profile', None)
    if profile is None:
        return False

    if getattr(profile, 'is_super_admin', False):
        return True

    legacy = (getattr(profile, 'role', None) or '').strip()
    if legacy in _STOREWIDE_LEGACY_ROLES:
        return True

    role = getattr(profile, 'custom_role', None)
    name = (getattr(role, 'name', None) or '').strip()
    if name in _STOREWIDE_ROLE_NAMES:
        return True

    # Explicit grant — assign sales.view_all in Roles UI.
    try:
        if profile.has_permission('sales', 'view_all'):
            return True
    except Exception:
        pass

    return False


def own_sales_q(user):
    """Q filter: sales credited to this user as cashier or served_by."""
    from django.db.models import Q

    uid = getattr(user, 'pk', None) or getattr(user, 'id', None)
    if uid is None:
        return Q(pk__in=[])
    return Q(cashier_id=uid) | Q(served_by_id=uid)
