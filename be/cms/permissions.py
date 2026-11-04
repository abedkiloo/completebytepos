"""Who may read the public website API, and who may write website content."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
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


def presented_website_key(request) -> str:
    """The marketing site sends one shared key, as X-Website-Key or Bearer."""
    header = (request.headers.get('X-Website-Key') or '').strip()
    if header:
        return header
    auth = (request.headers.get('Authorization') or '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return ''


def website_key_matches(presented: str, expected: str) -> bool:
    if not presented or not expected or len(presented) != len(expected):
        return False
    return secrets.compare_digest(presented, expected)


class WebsiteKeyAuthentication(BaseAuthentication):
    """One key for the public product list and for website enquiries.

    A staff login is not accepted here. An empty server key refuses everyone.
    """

    def authenticate(self, request):
        expected = (getattr(settings, 'WEBSITE_API_KEY', '') or '').strip()
        presented = presented_website_key(request)
        if not website_key_matches(presented, expected):
            raise AuthenticationFailed('Website key required.')
        return (AnonymousUser(), None)

    def authenticate_header(self, request):
        return 'Bearer realm="website"'
