"""Who may propose vs approve pending changes."""

from __future__ import annotations

from approvals.registry import CHECKER_MODULE_BY_ACTION


def is_maker_checker_enabled() -> bool:
    from settings.models import StoreSettings

    store = StoreSettings.load()
    return bool(getattr(store, 'maker_checker_enabled', True))


def is_sales_maker_checker_active() -> bool:
    from approvals.sales_policy import is_sales_maker_checker_active as _active

    return _active()


def is_emergency_stock_mode() -> bool:
    from settings.models import StoreSettings

    store = StoreSettings.load()
    return bool(getattr(store, 'emergency_stock_mode', False))


def user_can_check(user, action_type: str) -> bool:
    """Checker: super admin/staff or has module ``approve`` for this action."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role == 'super_admin':
        return True
    module = CHECKER_MODULE_BY_ACTION.get(action_type, 'settings')
    if profile and profile.has_permission(module, 'approve'):
        return True
    if profile and profile.has_permission(module, 'manage'):
        return True
    return False


def user_may_approve_change(user, change) -> bool:
    if not user_can_check(user, change.action_type):
        return False
    if change.made_by_id and change.made_by_id == user.id:
        return bool(user.is_superuser)
    return True
