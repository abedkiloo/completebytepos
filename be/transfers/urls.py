from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MoneyTransferViewSet

router = DefaultRouter()
router.register(r'', MoneyTransferViewSet, basename='transfer')

urlpatterns = [
    path('', include(router.urls)),
]

