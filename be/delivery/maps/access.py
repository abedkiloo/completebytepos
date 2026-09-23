"""Who may see another driver's planned route map."""


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
