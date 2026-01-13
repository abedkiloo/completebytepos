from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AccountTypeViewSet, AccountViewSet, JournalEntryViewSet,
    TransactionViewSet, AccountingReportViewSet
)

router = DefaultRouter()
router.register(r'account-types', AccountTypeViewSet, basename='account-type')
router.register(r'accounts', AccountViewSet, basename='account')
router.register(r'journal-entries', JournalEntryViewSet, basename='journal-entry')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'reports', AccountingReportViewSet, basename='accounting-report')

urlpatterns = [
    path('', include(router.urls)),
]

