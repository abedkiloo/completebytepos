"""
Shared DRF pagination classes.
"""
from rest_framework.pagination import PageNumberPagination


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
    max_page_size = 200
