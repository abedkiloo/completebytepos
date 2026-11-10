"""User + profile write helpers (used by UserViewSet update)."""

from django.contrib.auth.models import User
from rest_framework.exceptions import PermissionDenied

from .models import UserProfile, Role
from accounts.module_settings import (
    users_enable_inline_role_assignment,
    users_show_phone,
)

# Django / profile fields that escalate authority. Only a real super admin
# may set these via the API (never self-service, never ordinary staff).
PRIVILEGE_USER_FIELDS = ('is_staff', 'is_superuser')
PRIVILEGE_PROFILE_ROLES = frozenset({'super_admin', 'admin'})


def actor_is_super_admin(actor) -> bool:
    """
    True when ``actor`` is a Django superuser or profile super admin.

    Args:
        actor: Authenticated user or None.

    Returns:
        bool — False for anonymous / missing profile.
    """
    if actor is None or not getattr(actor, 'is_authenticated', False):
        return False
    if getattr(actor, 'is_superuser', False):
        return True
    profile = getattr(actor, 'profile', None)
    return bool(profile and getattr(profile, 'is_super_admin', False))


def strip_privilege_escalation(payload: dict, profile_data: dict, *, actor) -> None:
    """
    Remove privilege fields unless the actor is a super admin.

    Mutates ``payload`` / ``profile_data`` in place. Non-super-admins cannot
    set ``is_staff``, ``is_superuser``, or elevate ``role`` to admin tiers.

    Args:
        payload: Django User field dict from ``prepare_user_write_data``.
        profile_data: Profile field dict (may include ``role``).
        actor: Request user performing the write.

    Returns:
        None.

    Raises:
        PermissionDenied: When a non-super-admin explicitly requests
            ``is_superuser=True`` or ``role`` in admin tiers (clear attack).
    """
    if actor_is_super_admin(actor):
        return

    for field in PRIVILEGE_USER_FIELDS:
        if field not in payload:
            continue
        # Reject explicit privilege grants; silently drop clears/false.
        if payload.get(field) in (True, 'true', 'True', 1, '1'):
            raise PermissionDenied(
                'Only a super admin can grant staff or superuser privileges.'
            )
        payload.pop(field, None)

    role = profile_data.get('role')
    if role in PRIVILEGE_PROFILE_ROLES:
        raise PermissionDenied(
            'Only a super admin can assign admin or super admin roles.'
        )


def prepare_user_write_data(data):
    """
    Split request body into Django User fields and profile fields.

    Drops blank password so partial updates do not fail validation.

    Args:
        data: Mapping or QueryDict from the request body.

    Returns:
        Tuple ``(user_payload, profile_data)``. Privilege stripping is applied
        by the caller via ``strip_privilege_escalation``.
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
        from utils.phone import PhoneNumberError, normalize_phone_number
        from rest_framework.exceptions import ValidationError as DrfValidationError

        try:
            profile.phone_number = normalize_phone_number(
                profile_data.get('phone_number') or ''
            )
        except PhoneNumberError as exc:
            raise DrfValidationError({'phone_number': str(exc)}) from exc
    if 'custom_role' in profile_data:
        profile.custom_role = None
    elif 'custom_role_id' in profile_data and users_enable_inline_role_assignment():
        try:
            role = Role.objects.get(pk=int(profile_data['custom_role_id']))
            profile.custom_role = role
        except (Role.DoesNotExist, TypeError, ValueError):
            pass
    profile.save()
