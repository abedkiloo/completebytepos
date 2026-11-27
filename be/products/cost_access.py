"""Who may see cost of goods and other operational secrets."""

from __future__ import annotations

COST_RESPONSE_KEYS = frozenset({
    'cost',
    'effective_cost',
    'unit_cost',
    'total_cost',
    'avg_unit_cost',
    'line_cogs',
    'cogs',
    'total_cogs',
    'cost_value',
    'inventory_value',
    'gross_profit',
    'margin_pct',
    'line_gross_profit',
    'profit_margin',
    'profit_amount',
    'total_value',
    'cost_missing',
    'unit_cost_snapshot',
})

# A supplier phone is an operational contact, not a selling price.
MANAGEMENT_ONLY_KEYS = frozenset({
    'supplier_contact',
})

_ADMIN_COST_ROLES = frozenset({'Super Admin', 'Admin', 'Administrator'})
_MANAGEMENT_ROLES = frozenset({
    'Super Admin', 'Admin', 'Administrator', 'Manager', 'Director',
})
_MANAGEMENT_LEGACY = frozenset({
    'super_admin', 'admin', 'manager', 'director',
})


def user_may_see_cost(user) -> bool:
    """
    Whether this person may see cost of goods.

    Args:
        user: Signed-in user, or None. Anonymous is False. A custom role
            name is 0–150 characters.

    Returns:
        bool: True for an admin or super admin, and for any other role
        that has ``products.view_cost`` or ``reports.profit`` checked.
        A manager and a sales person are False until that box is checked.
        No writes.

    Raises:
        None.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    legacy = (getattr(profile, 'role', '') or '').strip()
    if legacy in ('admin', 'super_admin'):
        return True
    custom = getattr(profile, 'custom_role', None)
    name = (getattr(custom, 'name', '') or '').strip() if custom is not None else ''
    if name in _ADMIN_COST_ROLES:
        return True
    has = getattr(profile, 'has_permission', None)
    if not callable(has):
        return False
    return bool(has('products', 'view_cost') or has('reports', 'profit'))


def user_is_management(user) -> bool:
    """
    Whether this person is management.

    Args:
        user: Signed-in user, or None. Anonymous is False.

    Returns:
        bool: True for a manager, director, admin, or super admin.
        A sales person and a field agent are False. No writes.

    Raises:
        None.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    legacy = (getattr(profile, 'role', '') or '').strip()
    if legacy in _MANAGEMENT_LEGACY:
        return True
    custom = getattr(profile, 'custom_role', None)
    name = (getattr(custom, 'name', '') or '').strip() if custom is not None else ''
    return name in _MANAGEMENT_ROLES


def redact_cost_fields(data, *, request=None):
    """
    Remove cost of goods from a response when this person may not see it.

    Args:
        data: A dict or list from a serializer. Nested dicts and lists are
            walked. At most a few hundred keys on a product or a sale.
        request: The HTTP request, or None. None leaves the payload
            unchanged so internal callers and tests without a request
            still see cost. An anonymous request is stripped.

    Returns:
        The same shape, without cost, margin, profit, and stock-value
        keys when the person may not see them. ``delivery_cost`` stays.
        ``pending_approval`` (including ``proposed_values.cost``) is kept so
        a maker can see the cost change they just queued. No writes.

    Raises:
        None.
    """
    if request is None or user_may_see_cost(getattr(request, 'user', None)):
        return data
    return _drop_keys(
        data,
        COST_RESPONSE_KEYS,
        preserve_under=frozenset({'pending_approval'}),
    )


def redact_operational_secrets(data, *, request=None):
    """
    Hide cost from non-admins and supplier contact from non-management.

    Args:
        data: Serializer payload. Nested dicts and lists are walked.
        request: HTTP request, or None. None leaves the payload unchanged.

    Returns:
        The payload with cost removed unless this person may see cost,
        and with ``supplier_contact`` removed unless they are management.
        No writes.

    Raises:
        None.
    """
    data = redact_cost_fields(data, request=request)
    if request is None:
        return data
    user = getattr(request, 'user', None)
    if user_is_management(user):
        return data
    return _drop_keys(data, MANAGEMENT_ONLY_KEYS)


def _drop_keys(value, keys, *, preserve_under: frozenset[str] | None = None):
    """
    Recursively remove ``keys`` from dict trees.

    Args:
        value: Dict, list, or scalar payload fragment.
        keys: Field names to drop (0–64 names typical for cost redaction).
        preserve_under: Top-level map keys whose nested trees are left intact
            (e.g. ``pending_approval``). None means drop everywhere.

    Returns:
        The same shape with matching keys removed outside preserved subtrees.

    Raises:
        None.
    """
    preserve = preserve_under or frozenset()
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in keys:
                continue
            if key in preserve:
                out[key] = item
            else:
                out[key] = _drop_keys(item, keys, preserve_under=preserve_under)
        return out
    if isinstance(value, list):
        return [_drop_keys(item, keys, preserve_under=preserve_under) for item in value]
    return value
