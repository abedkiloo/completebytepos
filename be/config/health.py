"""
Lightweight liveness check for Docker / load balancers.

Public entry points:
    - ``healthz`` — DB ping JSON endpoint
"""
from django.db import connection
from django.http import JsonResponse


def healthz(_request):
    """
    Verify the app can reach the database.

    Args:
        _request: Unused Django request.

    Returns:
        ``JsonResponse({'ok': True})`` when ``SELECT 1`` succeeds.

    Raises:
        Database errors propagate when the connection fails (non-200 to callers).
    """
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return JsonResponse({'ok': True})
