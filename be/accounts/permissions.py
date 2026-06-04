"""
Role-based access control primitives for the POS backend.

There are three layers of access enforcement here, designed to compose:

1. **`RequirePerm(module, action)`** - the workhorse. Class factory that returns
   a real DRF BasePermission subclass, so it can be used directly in
   ``permission_classes = [...]`` (DRF instantiates classes with no args).

   Usage:
       class SaleViewSet(viewsets.ModelViewSet):
           permission_classes = [IsAuthenticated, RequirePerm('sales', 'view')]

   For per-action gating, prefer ``RequirePermPerAction(...)`` from this module
   (see below) which can apply different module/action checks depending on the
   request method.

2. **`RequireModuleAccess(module)`** - lighter check; "does this user have ANY
   access to this module?". Used when the action granularity doesn't matter.

3. **`RequireModuleEnabled(module)`** - global module toggle ("is the suppliers
   module turned on for this tenant?"). Reads from ``ModuleSettings``.

These three layers can be combined - e.g. an inventory write needs the module
to be enabled (`RequireModuleEnabled`) AND the user to have create permission
(`RequirePerm`).

Backwards-compatible re-exports of the legacy ``HasPermission`` and
``HasModuleAccess`` parametrized classes are kept at the bottom so existing
usage in ``employees/views.py`` and ``suppliers/views.py`` keeps working.
"""

from rest_framework import permissions, status
from rest_framework.response import Response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Map of DRF action name -> permission action verb.
# Override per-view via ``RequirePermPerAction(...)``.
DEFAULT_ACTION_MAP = {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
    # @action endpoints default to 'view' unless they explicitly say otherwise
}


def _user_profile(request):
    """Return the request user's profile, or None if missing."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'profile', None)


def _has_permission(request, module, action):
    """Single source of truth for "does this request's user have <module.action>?"."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return False
    # Django superuser bypass — important: don't lock the OS owner out of their
    # own system because of a misconfigured Role.
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    return profile.has_permission(module, action)


def _has_module_access(request, module):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    return profile.has_module_access(module)


# ---------------------------------------------------------------------------
# RequirePerm — the headline factory
# ---------------------------------------------------------------------------

def RequirePerm(module, action):
    """
    Class factory that returns a DRF BasePermission subclass enforcing
    ``profile.has_permission(module, action)``.

    Designed to be used directly in ``permission_classes``:

        permission_classes = [IsAuthenticated, RequirePerm('sales', 'create')]

    The returned class:
      * Has a stable name ``RequirePerm_<module>_<action>`` so DRF error
        messages and DEBUG views point at the right rule.
      * Has a ``message`` attribute matching the module/action so 403 responses
        tell the user (and the developer in logs) which permission they lack.
      * Treats Django superusers as having every permission — see ``_has_permission``.
    """

    class _RequirePerm(permissions.BasePermission):
        # These two are read by DRF to render the 403 response body
        module_name = module
        action_name = action
        message = f"You do not have permission: {module}.{action}"

        def has_permission(self, request, view):
            return _has_permission(request, module, action)

    _RequirePerm.__name__ = f"RequirePerm_{module}_{action}"
    _RequirePerm.__qualname__ = _RequirePerm.__name__
    return _RequirePerm


def RequireModuleAccess(module):
    """
    Class factory: user has *any* access to ``module`` (any action on any
    permission inside it). Cheaper than a specific ``RequirePerm`` and useful
    for read-mostly viewsets where the action-granularity check is overkill.
    """

    class _RequireModuleAccess(permissions.BasePermission):
        module_name = module
        message = f"You do not have access to the {module} module."

        def has_permission(self, request, view):
            return _has_module_access(request, module)

    _RequireModuleAccess.__name__ = f"RequireModuleAccess_{module}"
    _RequireModuleAccess.__qualname__ = _RequireModuleAccess.__name__
    return _RequireModuleAccess


def RequireModuleEnabled(module):
    """
    Class factory: the named module is enabled in ModuleSettings.

    This is *tenant config*, not user role — it lets you globally turn off
    e.g. the suppliers or invoicing module and have every endpoint in that
    module short-circuit with 403 (instead of 404 or worse, silently failing).
    """

    class _RequireModuleEnabled(permissions.BasePermission):
        module_name = module
        message = f"The {module} module is disabled for this tenant."

        def has_permission(self, request, view):
            # Import here to avoid the AppRegistry "not ready" import cycle at
            # module load time.
            from settings.models import ModuleSettings
            return ModuleSettings.is_module_enabled(module)

    _RequireModuleEnabled.__name__ = f"RequireModuleEnabled_{module}"
    _RequireModuleEnabled.__qualname__ = _RequireModuleEnabled.__name__
    return _RequireModuleEnabled


# ---------------------------------------------------------------------------
# RequirePermPerAction — per-DRF-action gating without overriding get_permissions
# ---------------------------------------------------------------------------

def RequirePermPerAction(module, action_map=None, default=None):
    """
    Class factory that maps the DRF view ``action`` (``'list'``,
    ``'create'``, ``'update'``, ``'destroy'``, ``'partial_update'``, custom
    @actions) to permission action verbs and enforces them.

    Example - SaleViewSet:

        permission_classes = [
            IsAuthenticated,
            RequirePermPerAction('sales', {
                'list': 'view',
                'retrieve': 'view',
                'create': 'create',
                # 'destroy' deliberately omitted - we disable DELETE on Sales
                # at the http_method_names level.
                'void': 'delete',
                'refund': 'delete',
            }),
        ]

    The optional ``default`` argument is used when the view's action is not in
    the map; if ``default`` is None and the action is unknown, the request is
    denied (fail-closed).

    This is preferred over multiple ``RequirePerm`` entries because a single
    class call covers an entire viewset.
    """
    merged = dict(DEFAULT_ACTION_MAP)
    if action_map:
        merged.update(action_map)

    class _RequirePermPerAction(permissions.BasePermission):
        module_name = module
        action_map_attr = merged
        message = f"You do not have permission on the {module} module."

        def has_permission(self, request, view):
            view_action = getattr(view, 'action', None)
            # Anything that's not a viewset action (e.g. plain APIView) gets
            # the default treatment.
            perm_action = merged.get(view_action, default)
            if perm_action is None:
                # fail-closed: unknown action on a gated viewset = deny
                self.message = (
                    f"No permission rule configured for {module}.{view_action!r}."
                )
                return False
            self.message = f"You do not have permission: {module}.{perm_action}"
            return _has_permission(request, module, perm_action)

    _RequirePermPerAction.__name__ = f"RequirePermPerAction_{module}"
    _RequirePermPerAction.__qualname__ = _RequirePermPerAction.__name__
    return _RequirePermPerAction


# ---------------------------------------------------------------------------
# Boolean composition helpers
# ---------------------------------------------------------------------------

def RequireAny(*permission_classes):
    """
    Class factory that ORs several BasePermission classes together. DRF's
    default is AND - this lets you say "either an owner-level permission OR a
    cashier-with-a-specific-grant".

    Usage:
        permission_classes = [
            IsAuthenticated,
            RequireAny(IsSuperAdmin, RequirePerm('sales', 'manage')),
        ]
    """
    if not permission_classes:
        raise ValueError("RequireAny needs at least one permission class")

    class _RequireAny(permissions.BasePermission):
        message = "You do not have any of the required permissions."

        def has_permission(self, request, view):
            return any(p().has_permission(request, view) for p in permission_classes)

    _RequireAny.__name__ = "RequireAny_" + "_or_".join(p.__name__ for p in permission_classes)
    _RequireAny.__qualname__ = _RequireAny.__name__
    return _RequireAny


# ---------------------------------------------------------------------------
# Built-in admin checks (unchanged, just kept here for one-stop import)
# ---------------------------------------------------------------------------

class IsSuperAdmin(permissions.BasePermission):
    """Django superuser OR profile.is_super_admin."""
    message = "Super-admin access required."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        profile = getattr(user, 'profile', None)
        return bool(profile and profile.is_super_admin)


class IsAdmin(permissions.BasePermission):
    """Django staff/superuser OR profile.is_admin."""
    message = "Admin access required."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        profile = getattr(user, 'profile', None)
        return bool(profile and profile.is_admin)


# ---------------------------------------------------------------------------
# Legacy parametrized classes — kept for back-compat with the few callsites in
# employees/views.py and suppliers/views.py that invoke them from
# get_permissions(). New code should prefer the class factories above.
# ---------------------------------------------------------------------------

class CanViewAuditLog(permissions.BasePermission):
    """Managers and super admins may read the append-only audit log."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        from accounts.sensitive_edits import user_may_view_audit_log

        return user_may_view_audit_log(request.user)


class HasPermission(permissions.BasePermission):
    """Legacy: parametrized via __init__; only usable from get_permissions()."""

    def __init__(self, module, action):
        self.module = module
        self.action = action

    def has_permission(self, request, view):
        return _has_permission(request, self.module, self.action)


class HasModuleAccess(permissions.BasePermission):
    """Legacy: parametrized via __init__; only usable from get_permissions()."""

    def __init__(self, module):
        self.module = module

    def has_permission(self, request, view):
        return _has_module_access(request, self.module)


# ---------------------------------------------------------------------------
# Decorators for plain function views (kept; rewritten to share the helpers
# above and removed dead string formatting).
# ---------------------------------------------------------------------------

def check_permission(module, action):
    """Decorator: gate a view method behind ``profile.has_permission(module, action)``."""
    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response({'error': 'Authentication required'},
                                status=status.HTTP_401_UNAUTHORIZED)
            if not _has_permission(request, module, action):
                return Response({'error': f'Permission denied: {module}.{action}'},
                                status=status.HTTP_403_FORBIDDEN)
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def check_module_access(module):
    """Decorator: gate a view method behind module access."""
    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response({'error': 'Authentication required'},
                                status=status.HTTP_401_UNAUTHORIZED)
            if not _has_module_access(request, module):
                return Response({'error': f'Access denied to module: {module}'},
                                status=status.HTTP_403_FORBIDDEN)
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator
