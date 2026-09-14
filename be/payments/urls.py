from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PaymentIntentViewSet, daraja_callback

router = DefaultRouter()
router.register(r'intents', PaymentIntentViewSet, basename='payment-intent')

urlpatterns = [
    path('daraja/callback/', daraja_callback, name='daraja-callback'),
    path('', include(router.urls)),
]
