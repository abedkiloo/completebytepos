"""Who may see product unit cost / COGS on Excel and CSV downloads."""

from __future__ import annotations

from typing import Any, Optional


def user_may_export_product_cost(user) -> bool:
    """
    Whether this user may include product cost columns on file exports.

    An admin or super admin always can. Any other role can when
    ``products.view_cost`` or ``reports.profit`` is checked. Staff alone
    does not reveal cost.

    Args:
        user: Authenticated Django user, or None.

    Returns:
        True when cost/COGS columns should appear on product-bearing workbooks.
    """
    from products.cost_access import user_may_see_cost

    return user_may_see_cost(user)


def request_wants_file_export(request) -> bool:
    """
    True when the client asked for a downloadable report file.

    Args:
        request: DRF/Django request with optional ``format`` query param.

    Returns:
        True for pdf/xlsx/csv (and excel aliases); False when format absent/invalid.
    """
    if request is None:
        return False
    from reports.export import UnsupportedExportFormat, normalize_export_format

    params = getattr(request, 'query_params', None) or getattr(request, 'GET', None)
    raw = params.get('format') if params is not None else None
    try:
        return normalize_export_format(raw) is not None
    except UnsupportedExportFormat:
        return False


def should_preserve_product_cost_on_export(request) -> bool:
    """
    Admin downloading Excel/CSV/PDF should keep cost fields in the payload.

    Args:
        request: Authenticated report/sales export request.

    Returns:
        True when cost columns must not be stripped before the file is built.
    """
    if not request_wants_file_export(request):
        return False
    return user_may_export_product_cost(getattr(request, 'user', None))


def strip_product_cost_fields(row: dict[str, Any]) -> dict[str, Any]:
    """
    Remove cost/COGS keys from one product-like dict.

    Args:
        row: Mapping that may contain unit_cost, cogs, etc.

    Returns:
        Shallow copy without cost keys (empty dict when row is empty).
    """
    out = dict(row)
    for key in (
        'unit_cost',
        'avg_unit_cost',
        'line_cogs',
        'cogs',
        'total_cogs',
        'cost',
        'cost_value',
        'inventory_value',
        'gross_profit',
        'margin_pct',
        'line_gross_profit',
    ):
        out.pop(key, None)
    return out
