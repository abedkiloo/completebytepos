"""
URL configuration for CompleteBytePOS project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
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
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
