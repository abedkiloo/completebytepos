from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryStopViewSet,
    available_orders,
    claim_order,
    delivery_config,
    list_routes,
    retrieve_route,
    staff_route_geometry,
    staff_route_lookup,
    today_route,
    today_route_geometry,
)

router = DefaultRouter()
router.register(r'stops', DeliveryStopViewSet, basename='delivery-stop')

urlpatterns = [
    path(
        'routes/today/geometry/',
        today_route_geometry,
        name='delivery-route-today-geometry',
    ),
    path('routes/today/', today_route, name='delivery-route-today'),
    path(
        'routes/geometry/',
        staff_route_geometry,
        name='delivery-route-staff-geometry',
    ),
    path(
        'routes/lookup/',
        staff_route_lookup,
        name='delivery-route-staff-lookup',
    ),
    path('routes/', list_routes, name='delivery-route-list'),
    path('routes/<int:pk>/', retrieve_route, name='delivery-route-detail'),
    path('config/', delivery_config, name='delivery-config'),
    path('available/', available_orders, name='delivery-available'),
    path(
        'field-orders/<int:pk>/claim/',
        claim_order,
        name='delivery-claim-order',
    ),
    path('', include(router.urls)),
]
