"""Who may be assigned (or claim) a delivery.

Eligibility is the Delivery *permission*, not the Delivery Driver role name.
Admin can assign a sales person, a dedicated driver, or anyone whose role
has ``delivery.update``.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist


def user_can_do_delivery(user) -> bool:
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
