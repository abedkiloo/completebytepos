"""Temporary passwords set by admins must be changed on next login."""

from django.contrib.auth.models import User

from .models import UserProfile

MIN_PASSWORD_LENGTH = 6


def user_must_change_password(user) -> bool:
    profile = getattr(user, 'profile', None)
    return bool(profile and getattr(profile, 'must_change_password', False))


def set_must_change_password(user: User, value: bool) -> None:
    profile = getattr(user, 'profile', None)
    if profile is None:
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': 'cashier', 'must_change_password': value},
        )
        if profile.must_change_password == value:
            return
    if profile.must_change_password == value:
        return
    profile.must_change_password = value
    profile.save(update_fields=['must_change_password', 'updated_at'])


def validate_new_password(new_password, *, user=None, reject_reuse=False):
    """Return an error string, or None if the password is acceptable."""
    if new_password is None or str(new_password).strip() == '':
        return 'new_password is required'
    password = str(new_password)
    if len(password) < MIN_PASSWORD_LENGTH:
        return f'Password must be at least {MIN_PASSWORD_LENGTH} characters'
    if reject_reuse and user is not None and user.check_password(password):
        return 'Choose a different password from the one you just used'
    return None
