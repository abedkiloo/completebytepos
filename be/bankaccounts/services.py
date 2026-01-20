"""
Bank Accounts service layer - handles all bank account business logic
"""
from typing import Optional, List, Dict, Any
from django.db.models import Q, Count, QuerySet
from .models import BankAccount, BankTransaction
from services.base import BaseService


class BankAccountService(BaseService):
    """Service for bank account operations"""
    
    def __init__(self):
        super().__init__(BankAccount)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for bank account listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
        
        Returns:
            QuerySet of bank accounts with transaction_count annotation
        """
        queryset = self.model.objects.annotate(transaction_count=Count('transactions'))
        
        if not filters:
            return queryset
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        return queryset.order_by('bank_name', 'account_name')
    
    def update_balance(self, account: BankAccount) -> BankAccount:
        """Update account balance from transactions"""
        account.update_balance()
        return account


class BankTransactionService(BaseService):
    """Service for bank transaction operations"""
    
    def __init__(self):
        super().__init__(BankTransaction)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for transaction listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - account: int (account ID)
                - date_from: str (date string)
                - date_to: str (date string)
        
        Returns:
            QuerySet of transactions with proper select_related
        """
        queryset = self.model.objects.all().select_related('bank_account', 'created_by')
        
        if not filters:
            return queryset.order_by('-transaction_date', '-created_at')
        
        account = filters.get('account')
        if account:
            try:
                queryset = queryset.filter(bank_account_id=int(account))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(transaction_date__gte=date_from)
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(transaction_date__lte=date_to)
        
        return queryset.order_by('-transaction_date', '-created_at')
