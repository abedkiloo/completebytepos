"""Who may propose vs approve pending changes."""

from __future__ import annotations

from approvals.registry import (
    ACTION_DEBT_COLLECTION,
    ACTION_SALE_BACKFILL,
    ACTION_SALE_COMPLETE,
    ACTION_SALE_REFUND,
    ACTION_SALE_ROLLBACK,
    CHECKER_MODULE_BY_ACTION,
)


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
    if action_type in (ACTION_SALE_ROLLBACK, ACTION_SALE_REFUND):
        # Void/refund and rollback are admin-gated even when a manager is staff.
        return user_has_admin_checker_override(user) or (
            getattr(user, 'profile', None)
            and user.profile.has_permission('settings', 'approve')
        )
    if action_type == ACTION_DEBT_COLLECTION:
        # Staff managers still need the Roles checkbox to approve collections.
        return user_has_admin_checker_override(user) or (
            getattr(user, 'profile', None)
            and user.profile.has_permission('debt_management', 'approve')
        )
    if action_type == ACTION_SALE_COMPLETE:
        return user_has_admin_checker_override(user) or (
            getattr(user, 'profile', None)
            and user.profile.has_permission('sales', 'approve')
        )
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


def user_has_admin_checker_override(user) -> bool:
    """Only Admin/Super Admin may approve a change they submitted."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role in ('admin', 'super_admin'))


PAST_DATED_ADMIN_ONLY_MESSAGE = (
    'This item is dated before today. Only an admin can approve or return past-dated items.'
)

_PAST_APPROVER_ROLE_NAMES = frozenset({'Super Admin', 'Admin', 'Administrator'})


def user_may_approve_past_items(user) -> bool:
    """Admin / Super Admin only — managers approve today's items, admins anything older."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    if (getattr(profile, 'role', None) or '') in ('admin', 'super_admin'):
        return True
    role = getattr(profile, 'custom_role', None)
    return (getattr(role, 'name', None) or '').strip() in _PAST_APPROVER_ROLE_NAMES


def _local_day(value):
    """Date / datetime / ISO string -> local calendar date (None if unknown)."""
    from datetime import date, datetime

    from django.utils import timezone
    from django.utils.dateparse import parse_date, parse_datetime

    if value in (None, ''):
        return None
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            return parse_date(value[:10])
        value = parsed
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return timezone.localtime(value).date()
    if isinstance(value, date):
        return value
    return None


def earliest_business_day(*values):
    days = [d for d in (_local_day(v) for v in values) if d is not None]
    return min(days) if days else None


def is_past_dated(*values) -> bool:
    """True when the earliest of the given dates falls before today (local)."""
    from django.utils import timezone

    day = earliest_business_day(*values)
    return bool(day and day < timezone.localdate())


def change_business_dates(change) -> list:
    """Dates that place a pending change on a business day (request day + item day)."""
    dates = [change.made_at]
    payload = change.apply_payload or {}
    if change.action_type == ACTION_SALE_BACKFILL:
        dates.append(payload.get('occurred_at'))
    elif change.action_type == ACTION_SALE_COMPLETE:
        from sales.models import Sale

        occurred = (
            Sale.objects.filter(pk=change.entity_id)
            .values_list('occurred_at', flat=True)
            .first()
        )
        dates.append(occurred)
    return dates


def change_is_past_dated(change) -> bool:
    return is_past_dated(*change_business_dates(change))


def user_may_approve_dated_item(user, *dates) -> bool:
    return user_may_approve_past_items(user) or not is_past_dated(*dates)


def user_may_approve_change(user, change) -> bool:
    if not user_can_check(user, change.action_type):
        return False
    if change_is_past_dated(change) and not user_may_approve_past_items(user):
        return False
    if change.made_by_id and change.made_by_id == user.id:
        return user_has_admin_checker_override(user)
    return True
