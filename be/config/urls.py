"""
URL configuration for CompleteBytePOS project.
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.views.static import serve
from django.http import HttpResponse
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from accounts.throttles import LoginRateThrottle
from config.health import healthz


def _authenticated_media_serve(request, path, document_root=None, show_indexes=False):
    """
    Serve media only when the caller is authenticated (session or JWT).

    Args:
        request: Django request (may carry ``Authorization: Bearer``).
        path: Relative path under MEDIA_ROOT.
        document_root: Absolute media root.
        show_indexes: Passed through to ``django.views.static.serve``.

    Returns:
        File response, or HTTP 401 when unauthenticated.
    """
    user = None
    if getattr(request, 'user', None) is not None and request.user.is_authenticated:
        user = request.user
    if user is None:
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication

            result = JWTAuthentication().authenticate(request)
            if result:
                user = result[0]
        except Exception:
            user = None
    if user is None:
        return HttpResponse('Authentication required.', status=401)
    return serve(
        request, path, document_root=document_root, show_indexes=show_indexes,
    )


def media_urlpatterns():
    """
    Serve uploaded files from MEDIA_ROOT.

    ``django.conf.urls.static.static()`` is a no-op when DEBUG=False, so UAT
    and production must register ``serve`` explicitly when SERVE_MEDIA is on.
    When ``MEDIA_REQUIRE_AUTH`` is True, anonymous clients get 401.
    """
    if not (settings.DEBUG or getattr(settings, 'SERVE_MEDIA', True)):
        return []
    prefix = (settings.MEDIA_URL or '/media/').strip('/')
    view = (
        _authenticated_media_serve
        if getattr(settings, 'MEDIA_REQUIRE_AUTH', False)
        else serve
    )
    return [
        re_path(
            rf'^{prefix}/(?P<path>.*)$',
            view,
            {'document_root': str(settings.MEDIA_ROOT)},
        ),
    ]


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/healthz/', healthz, name='healthz'),
    path(
        'api/token/',
        TokenObtainPairView.as_view(throttle_classes=[LoginRateThrottle]),
        name='token_obtain_pair',
    ),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/products/', include('products.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/accounts/', include('accounts.urls')),
    path('api/settings/', include('settings.urls')),  # Settings app endpoints
    path('api/reports/', include('reports.urls')),
    path('api/barcodes/', include('barcodes.urls'), name='barcodes'),
    path('api/expenses/', include('expenses.urls')),
    path('api/accounting/', include('accounting.urls')),
    path('api/income/', include('income.urls')),
    path('api/bank-accounts/', include('bankaccounts.urls')),
    path('api/transfers/', include('transfers.urls')),
    path('api/suppliers/', include('suppliers.urls')),
    path('api/employees/', include('employees.urls')),
    path('api/appraisals/', include('appraisals.urls')),
    path('api/payroll/', include('payroll.urls')),
    path('api/daily-notes/', include('daily_notes.urls')),
    path('api/visits/', include('agents.urls')),
    path('api/agents/', include('agents.urls')),  # alias — same viewsets
    path('api/dispatch/', include('dispatch.urls')),
    path('api/delivery/', include('delivery.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/messaging/', include('messaging.urls')),
    path('api/public/website/', include('cms.urls_public')),
    path('api/public/', include('payments.urls_public')),
    path('api/cms/', include('cms.urls')),
    path('api/approvals/', include('approvals.urls')),
] + media_urlpatterns()
