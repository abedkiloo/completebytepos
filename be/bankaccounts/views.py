from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count
from .models import BankAccount, BankTransaction
from .serializers import BankAccountSerializer, BankTransactionSerializer


class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.all().select_related('created_by')
    serializer_class = BankAccountSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['account_name', 'account_number', 'bank_name']
    ordering_fields = ['bank_name', 'account_name', 'created_at']
    ordering = ['bank_name', 'account_name']

    def get_queryset(self):
        queryset = BankAccount.objects.annotate(
            transaction_count=Count('transactions')
        )
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def update_balance(self, request, pk=None):
        """Manually update account balance"""
        account = self.get_object()
        account.update_balance()
        serializer = self.get_serializer(account)
        return Response(serializer.data)


class BankTransactionViewSet(viewsets.ModelViewSet):
    queryset = BankTransaction.objects.all().select_related('bank_account', 'created_by')
    serializer_class = BankTransactionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['transaction_number', 'description', 'reference']
    ordering_fields = ['transaction_date', 'amount', 'created_at']
    ordering = ['-transaction_date', '-created_at']

    def get_queryset(self):
        queryset = BankTransaction.objects.all().select_related('bank_account', 'created_by')
        account = self.request.query_params.get('account', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if account:
            queryset = queryset.filter(bank_account_id=account)
        if date_from:
            queryset = queryset.filter(transaction_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(transaction_date__lte=date_to)
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
