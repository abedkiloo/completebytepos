from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SaleViewSet, InvoiceViewSet, PaymentViewSet, CustomerViewSet
from .call_book_views import (
    CallBookHoldView,
    CallBookMarkView,
    CallBookPlanView,
    CallBookView,
)

# Create router and register viewsets
# IMPORTANT: Register more specific routes BEFORE less specific ones
router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')
# Register sales last as it uses empty string pattern
router.register(r'', SaleViewSet, basename='sale')

urlpatterns = [
    path('call-book/', CallBookView.as_view(), name='call-book'),
    path('call-book/plan/', CallBookPlanView.as_view(), name='call-book-plan'),
    path('call-book/<int:customer_id>/mark/', CallBookMarkView.as_view(), name='call-book-mark'),
    path('call-book/<int:customer_id>/hold/', CallBookHoldView.as_view(), name='call-book-hold'),
    path('', include(router.urls)),
]
