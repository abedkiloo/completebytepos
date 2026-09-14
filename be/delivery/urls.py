from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeliveryStopViewSet, delivery_config, today_route

router = DefaultRouter()
router.register(r'stops', DeliveryStopViewSet, basename='delivery-stop')

urlpatterns = [
    path('routes/today/', today_route, name='delivery-route-today'),
    path('config/', delivery_config, name='delivery-config'),
    path('', include(router.urls)),
]
