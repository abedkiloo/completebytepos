"""User + profile write helpers (used by UserViewSet update)."""

from django.contrib.auth.models import User

from .models import UserProfile, Role
from accounts.module_settings import (
    users_enable_inline_role_assignment,
    users_show_phone,
)


def prepare_user_write_data(data):
    """
    Split request body into Django User fields and profile fields.
    Drops blank password so partial updates do not fail validation.
    """
    if hasattr(data, 'copy'):
        payload = data.copy()
    else:
        payload = dict(data)

    profile_data = {}
    if 'role' in payload:
        profile_data['role'] = payload.pop('role')
    if 'phone_number' in payload:
        profile_data['phone_number'] = payload.pop('phone_number')
    if 'custom_role_id' in payload:
        raw = payload.pop('custom_role_id')
        if raw in ('', None):
            profile_data['custom_role'] = None
        else:
            profile_data['custom_role_id'] = raw
    if payload.get('password') in ('', None):
        payload.pop('password', None)
    return payload, profile_data


def apply_profile_updates(user: User, profile_data: dict) -> None:
    """Persist profile fields sent from the user admin form."""
    if not profile_data:
        return

    if not hasattr(user, 'profile') or user.profile is None:
        UserProfile.objects.create(
            user=user,
            role=profile_data.get('role', 'cashier'),
        )

    profile = user.profile
    if 'role' in profile_data and users_enable_inline_role_assignment():
        profile.role = profile_data['role']
    if 'phone_number' in profile_data and users_show_phone():
        profile.phone_number = profile_data.get('phone_number') or ''
    if 'custom_role' in profile_data:
        profile.custom_role = None
    elif 'custom_role_id' in profile_data and users_enable_inline_role_assignment():
        try:
            role = Role.objects.get(pk=int(profile_data['custom_role_id']))
            profile.custom_role = role
        except (Role.DoesNotExist, TypeError, ValueError):
            pass
    profile.save()
