"""Who may see another driver's planned route map and past deliveries."""

from datetime import date

HISTORY_ROLE_NAMES = frozenset(
    {
        'Super Admin',
        'Manager',
        'Admin',
        'Administrator',
    }
)


def user_may_view_agent_route(user, agent_id: int) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    try:
        agent_id = int(agent_id)
    except (TypeError, ValueError):
        return False
    if user.id == agent_id:
        return True
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    if getattr(profile, 'is_super_admin', False) or getattr(profile, 'is_manager', False):
        return True
    has_perm = getattr(profile, 'has_permission', None)
    if callable(has_perm) and has_perm('dispatch', 'view'):
        return True
    return False


def _custom_role_name(profile) -> str:
    role = getattr(profile, 'custom_role', None)
    if role is None:
        return ''
    name = getattr(role, 'name', None)
    if not isinstance(name, str):
        return ''
    return name.strip()


def user_may_view_delivery_history(user) -> bool:
    """Past routes / completed stops: Super Admin, Manager, Admin, or delivery.history."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    if getattr(profile, 'is_super_admin', False):
        return True
    has_perm = getattr(profile, 'has_permission', None)
    if callable(has_perm) and has_perm('delivery', 'history'):
        return True
    if _custom_role_name(profile) in HISTORY_ROLE_NAMES:
        return True
    if getattr(profile, 'role', '') in ('super_admin', 'admin'):
        return True
    return False


def user_may_view_route_on_date(user, agent_id: int, route_date: date | None) -> bool:
    """Today (and future) uses the live staff map rule. Past days need history."""
    if not user_may_view_agent_route(user, agent_id):
        return False
    if route_date is None:
        return True
    from django.utils import timezone

    if route_date >= timezone.localdate():
        return True
    return user_may_view_delivery_history(user)
