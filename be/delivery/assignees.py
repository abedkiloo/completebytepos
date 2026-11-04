"""
Delivery assignee eligibility (permission-based, not role name).

Public entry points:
    - ``user_can_do_delivery`` / ``eligible_delivery_assignees`` — assign + claim gates
    - ``user_is_delivery_driver`` — alias of ``user_can_do_delivery``

Rule: active user profile with ``delivery.update`` on an active custom role.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist


def user_can_do_delivery(user) -> bool:
    """
    Return whether ``user`` may run delivery stops or be assigned orders.

    Args:
        user: Django user; inactive or missing profile → False.

    Returns:
        True when profile is active and ``has_permission('delivery', 'update')``.
    """
    if user is None or not getattr(user, 'is_active', False):
        return False
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        return False
    if not getattr(profile, 'is_active', False):
        return False
    return bool(profile.has_permission('delivery', 'update'))


# Older assign-path name. Same rule: delivery.update, any role.
user_is_delivery_driver = user_can_do_delivery


def eligible_delivery_assignees():
    """
    List active users eligible for dispatch assign and driver directory APIs.

    Returns:
        ``QuerySet`` of ``User`` ordered by name, distinct, with profile/role
        prefetched. Empty when no roles grant ``delivery.update``.
    """
    return (
        User.objects.filter(
            is_active=True,
            profile__is_active=True,
            profile__custom_role__is_active=True,
            profile__custom_role__permissions__module='delivery',
            profile__custom_role__permissions__action='update',
        )
        .select_related('profile', 'profile__custom_role')
        .distinct()
        .order_by('first_name', 'last_name', 'username')
    )
