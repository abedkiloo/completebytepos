from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .order_views import FieldOrderViewSet
from .views import CustomerSiteViewSet

router = DefaultRouter()
router.register(r'sites', CustomerSiteViewSet, basename='customer-site')
router.register(r'field-orders', FieldOrderViewSet, basename='field-order')

urlpatterns = [
    path('', include(router.urls)),
]
