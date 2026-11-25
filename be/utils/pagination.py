"""
Shared DRF pagination classes.
"""
import os

from rest_framework.pagination import PageNumberPagination


def _max_page_size() -> int:
    """
    Cap for ``?page_size=`` across list APIs.

    Returns:
        Integer 20–500 from ``API_MAX_PAGE_SIZE`` (default 200). Keeps
        POS/catalog usable while blocking abusive full-table dumps.
    """
    raw = (os.getenv('API_MAX_PAGE_SIZE') or '200').strip()
    try:
        value = int(raw)
    except ValueError:
        return 200
    return max(20, min(500, value))


class StandardResultsSetPagination(PageNumberPagination):
    """
    Default pagination for the API.

    Lets clients override the page size via ``?page_size=N`` (capped at
    ``max_page_size`` to prevent abusive requests that would force the
    backend to materialize huge querysets). The vanilla DRF
    ``PageNumberPagination`` ignores ``?page_size``, which both surprises
    frontend integrators and made paginated tables on the FE harder to
    tune. Cashier and operator views often want 50–100 rows per page;
    admin dashboards sometimes want 20. ``page_size_query_param`` covers
    both without a per-view subclass.
    """

    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = _max_page_size()
