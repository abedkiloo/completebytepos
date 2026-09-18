"""Who may see store-wide sales vs only their own."""

from __future__ import annotations


def user_sees_all_sales(user) -> bool:
    """
    Managers / admins see every cashier's sales.
    Sales agents (Sales Personnel, Field Sales, etc.) only see their own.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'is_staff', False):
        return True

    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    if getattr(profile, 'is_super_admin', False):
        return True
    if getattr(profile, 'is_admin', False):
        return True
    if getattr(profile, 'is_manager', False):
        return True

    role = getattr(profile, 'custom_role', None)
    name = (getattr(role, 'name', None) or '').strip()
    if name in {
        'Super Admin',
        'Manager',
        'Admin',
        'Administrator',
    }:
        return True
    return False


def own_sales_q(user):
    """Q filter: sales credited to this user as cashier or served_by."""
    from django.db.models import Q

    uid = getattr(user, 'pk', None) or getattr(user, 'id', None)
    if uid is None:
        return Q(pk__in=[])
    return Q(cashier_id=uid) | Q(served_by_id=uid)
