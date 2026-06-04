from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count
from .models import BankAccount, BankTransaction
from .serializers import BankAccountSerializer, BankTransactionSerializer
from .services import BankAccountService, BankTransactionService
from accounts.permissions import RequirePermPerAction
from utils.audit_helpers import audited_perform_create
from utils.audit_mixin import AuditedModelViewSetMixin


BANK_ACCOUNTS_PERMS = RequirePermPerAction('bank_accounts', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
    'update_balance': 'update',
})


class BankAccountViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = BankAccount.objects.all().select_related('created_by')
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated, BANK_ACCOUNTS_PERMS]
    audit_module = 'bank_accounts'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['account_name', 'account_number', 'bank_name']
    ordering_fields = ['bank_name', 'account_name', 'created_at']
    ordering = ['bank_name', 'account_name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.account_service = BankAccountService()

    def get_queryset(self):
        """Get queryset using service layer"""
        filters = {}
        if 'is_active' in self.request.query_params:
            filters['is_active'] = self.request.query_params.get('is_active')
        return self.account_service.build_queryset(filters)

    def perform_create(self, serializer):
        audited_perform_create(self, serializer, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def update_balance(self, request, pk=None):
        """Manually update account balance - thin view, business logic in service"""
        account = self.get_object()
        updated_account = self.account_service.update_balance(account)
        serializer = self.get_serializer(updated_account)
        return Response(serializer.data)


class BankTransactionViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = BankTransaction.objects.all().select_related('bank_account', 'created_by')
    serializer_class = BankTransactionSerializer
    permission_classes = [IsAuthenticated, BANK_ACCOUNTS_PERMS]
    audit_module = 'bank_accounts'
    # Bank transactions are part of the audit trail - immutable via API.
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['transaction_number', 'description', 'reference']
    ordering_fields = ['transaction_date', 'amount', 'created_at']
    ordering = ['-transaction_date', '-created_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction_service = BankTransactionService()

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['account', 'date_from', 'date_to']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.transaction_service.build_queryset(filters)

    def perform_create(self, serializer):
        audited_perform_create(self, serializer, created_by=self.request.user)
