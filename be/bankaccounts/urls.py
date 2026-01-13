from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BankAccountViewSet, BankTransactionViewSet

router = DefaultRouter()
router.register(r'accounts', BankAccountViewSet, basename='bank-account')
router.register(r'transactions', BankTransactionViewSet, basename='bank-transaction')

urlpatterns = [
    path('', include(router.urls)),
]

