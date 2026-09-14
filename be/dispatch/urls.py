from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DispatchQueueViewSet

router = DefaultRouter()
router.register(r'field-orders', DispatchQueueViewSet, basename='dispatch-field-order')

urlpatterns = [
    path('', include(router.urls)),
    # Alias matching API contract: GET /dispatch/queue/
    path(
        'queue/',
        DispatchQueueViewSet.as_view({'get': 'queue'}),
        name='dispatch-queue',
    ),
]
