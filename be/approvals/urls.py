from django.urls import path, include
from rest_framework.routers import DefaultRouter

from approvals.views import PendingChangeViewSet

router = DefaultRouter()
router.register(r'pending-changes', PendingChangeViewSet, basename='pending-change')

urlpatterns = [
    path('', include(router.urls)),
]
