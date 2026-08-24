"""Lightweight liveness check for Docker / load balancers."""
from django.db import connection
from django.http import JsonResponse


def healthz(_request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return JsonResponse({'ok': True})
