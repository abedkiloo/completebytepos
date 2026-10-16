from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .checkpoint_views import StockCheckpointViewSet
from .views import StockMovementViewSet

router = DefaultRouter()
router.register(r'checkpoints', StockCheckpointViewSet, basename='stock-checkpoint')
router.register(r'', StockMovementViewSet, basename='stock-movement')

urlpatterns = [
    path('', include(router.urls)),
]
