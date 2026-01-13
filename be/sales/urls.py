from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SaleViewSet, InvoiceViewSet, PaymentViewSet, CustomerViewSet

# Create router and register viewsets
# IMPORTANT: Register more specific routes BEFORE less specific ones
router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')
# Register sales last as it uses empty string pattern
router.register(r'', SaleViewSet, basename='sale')

urlpatterns = [
    path('', include(router.urls)),
]
