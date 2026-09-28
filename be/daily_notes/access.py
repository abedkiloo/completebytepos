"""Who may access daily notes and see all staff entries."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from daily_notes.module_settings import (
    daily_notes_allow_manager_view_all,
    daily_notes_allow_sales_access,
    daily_notes_allow_sales_view_all,
)
from products.catalog_access import resolve_user_role


def _user_has_perm(user, module: str, action: str) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    return profile.has_permission(module, action)


def _user_has_sales_desk(user) -> bool:
    """POS / sales history — returned-sale sticky notes live on this desk."""
    return _user_has_perm(user, 'sales', 'view') or _user_has_perm(user, 'pos', 'view')


def user_may_access_daily_notes(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    has_notes = _user_has_perm(user, 'daily_notes', 'view')
    if not has_notes and not _user_has_sales_desk(user):
        return False
    role = resolve_user_role(user)
    if role == 'sales' and not daily_notes_allow_sales_access():
        return False
    return True


def user_may_view_all_daily_notes(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if profile is not None and (
        getattr(profile, 'is_super_admin', False)
        or getattr(profile, 'role', None) in ('admin', 'super_admin')
    ):
        return True
    if _user_has_perm(user, 'daily_notes', 'view_all'):
        role = resolve_user_role(user)
        if role == 'super_admin':
            return True
        if role == 'manager' and daily_notes_allow_manager_view_all():
            return True
        if role == 'sales' and daily_notes_allow_sales_view_all():
            return True
    return False


class AllowDailyNotesDeskAccess(BasePermission):
    """Sales/POS staff may open Daily notes without a separate daily_notes.view grant."""

    message = 'Daily notes are not available for your role.'

    def has_permission(self, request, view):
        return user_may_access_daily_notes(getattr(request, 'user', None))
