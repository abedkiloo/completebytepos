"""Who may write website blog posts."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

_ADMIN_ROLE_NAMES = frozenset({'Super Admin', 'Admin', 'Administrator'})
_ADMIN_LEGACY_ROLES = frozenset({'super_admin', 'admin'})


def user_can_manage_website(user) -> bool:
    """Admins always; anyone else needs ``website.manage`` on their role."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    if getattr(profile, 'is_super_admin', False):
        return True
    if (getattr(profile, 'role', None) or '').strip() in _ADMIN_LEGACY_ROLES:
        return True
    role = getattr(profile, 'custom_role', None)
    if (getattr(role, 'name', None) or '').strip() in _ADMIN_ROLE_NAMES:
        return True
    try:
        return bool(profile.has_permission('website', 'manage'))
    except Exception:
        return False


class CanManageWebsite(BasePermission):
    message = 'You do not have permission to manage website content.'

    def has_permission(self, request, view):
        return user_can_manage_website(request.user)
