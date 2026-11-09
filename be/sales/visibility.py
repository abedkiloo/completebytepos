"""Who may see store-wide sales vs only their own."""

from __future__ import annotations

from accounts.role_definitions import ROLE_FIELD_AGENT

# Roles that always see every seller's sales (without needing sales.view_all).
_STOREWIDE_ROLE_NAMES = frozenset({
    'Super Admin',
    'Admin',
    'Administrator',
    'Manager',
})

_STOREWIDE_LEGACY_ROLES = frozenset({
    'super_admin',
    'admin',
})

# Legacy UserProfile.role values that mean Field Sales.
_FIELD_AGENT_LEGACY_ROLES = frozenset({
    'field_sales',
    'field_agent',
})


def user_sees_all_sales(user) -> bool:
    """
    Store-wide sales (today / week / month / history totals).

    Default: Super Admin / Admin / Manager.
    Sales staff see only their own sales (cashier or served_by).
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
    # Legacy manager only counts when no custom role overrides it (e.g. Dispatcher).
    if role is None and legacy == 'manager':
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


def user_sees_all_debt(user) -> bool:
    """
    Store-wide Debt Management (every customer still owing).

    Managers / admins (store-wide sales) always see every debtor.

    Anyone who can collect debt (``debt_management.update``) also sees the full
    board — customer profiles already show wallet debt for every customer, and
    hiding those rows from Debt Management blocked payment.

    Field Sales are excluded: they only see debt for customers they onboarded
    (see ``user_limited_to_own_customers`` / ``_visible_debtor_customer_ids``).

    Args:
        user: Authenticated Django user, or None.

    Returns:
        bool — True when the full debtor board is allowed.
    """
    if user_limited_to_own_customers(user):
        return False
    if user_sees_all_sales(user):
        return True
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    try:
        return bool(profile.has_permission('debt_management', 'update'))
    except Exception:
        return False


def user_sees_all_customers(user) -> bool:
    """
    Store-wide customer directory (every duka / account).

    Same base as store-wide sales (admin / manager), plus explicit
    ``customers.view_all`` on the role.

    Args:
        user: Authenticated Django user, or None.

    Returns:
        bool — True when the user may list any customer.
    """
    if user_sees_all_sales(user):
        return True
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    try:
        if profile.has_permission('customers', 'view_all'):
            return True
    except Exception:
        pass
    return False


def is_field_sales_user(user) -> bool:
    """
    True when the user's job role is Field Sales (or legacy field_sales).

    Args:
        user: Authenticated Django user, or None.

    Returns:
        bool — False when unauthenticated, missing profile, or not Field Sales.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    role = getattr(profile, 'custom_role', None)
    name = (getattr(role, 'name', None) or '').strip()
    if name == ROLE_FIELD_AGENT:
        return True
    legacy = (getattr(profile, 'role', None) or '').strip()
    return legacy in _FIELD_AGENT_LEGACY_ROLES


def user_limited_to_own_customers(user) -> bool:
    """
    True when the user may only see customers they onboarded (``created_by``).

    v1: Field Sales only. Managers / admins / ``customers.view_all`` stay store-wide.
    Shop Sales Personnel keep the full directory for counter POS.

    Args:
        user: Authenticated Django user, or None.

    Returns:
        bool — True when customer querysets must filter to ``created_by=user``.
    """
    if user_sees_all_customers(user):
        return False
    return is_field_sales_user(user)


def own_customers_q(user):
    """
    Q filter: customers onboarded by this user (``Customer.created_by``).

    Args:
        user: Django user with a primary key.

    Returns:
        ``django.db.models.Q`` matching ``created_by_id``. Empty pk → match nothing.
    """
    from django.db.models import Q

    uid = getattr(user, 'pk', None) or getattr(user, 'id', None)
    if uid is None:
        return Q(pk__in=[])
    return Q(created_by_id=uid)


def apply_customer_visibility(queryset, user):
    """
    Restrict a Customer queryset for Field Sales to their onboarded dukas.

    Args:
        queryset: ``Customer`` queryset (or compatible).
        user: Request user.

    Returns:
        Filtered queryset when limited; otherwise the original queryset.
    """
    if user_limited_to_own_customers(user):
        return queryset.filter(own_customers_q(user))
    return queryset
