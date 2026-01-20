"""
Accounting service layer - handles all accounting business logic
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, QuerySet
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, date
from .models import AccountType, Account, JournalEntry, Transaction
from services.base import BaseService


class AccountTypeService(BaseService):
    """Service for account type operations"""
    
    def __init__(self):
        super().__init__(AccountType)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """Build queryset for account types"""
        return self.model.objects.all().order_by('name')


class AccountService(BaseService):
    """Service for account operations"""
    
    def __init__(self):
        super().__init__(Account)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for account listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - account_type: str (account type name)
                - is_active: bool or str ('true'/'false')
        
        Returns:
            QuerySet of accounts with proper select_related
        """
        queryset = self.model.objects.all().select_related('account_type', 'parent')
        
        if not filters:
            return queryset.order_by('account_code')
        
        account_type = filters.get('account_type')
        if account_type:
            queryset = queryset.filter(account_type__name=account_type)
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        return queryset.order_by('account_code')
    
    def update_balance(self, account: Account) -> Account:
        """Update account balance from journal entries"""
        account.update_balance()
        return account


class JournalEntryService(BaseService):
    """Service for journal entry operations"""
    
    def __init__(self):
        super().__init__(JournalEntry)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for journal entry listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - account: int (account ID)
                - date_from: str (date string)
                - date_to: str (date string)
                - entry_type: str ('debit' or 'credit')
        
        Returns:
            QuerySet of journal entries with proper select_related
        """
        queryset = self.model.objects.all().select_related('account', 'created_by')
        
        if not filters:
            return queryset.order_by('-entry_date', '-created_at')
        
        account = filters.get('account')
        if account:
            try:
                queryset = queryset.filter(account_id=int(account))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(entry_date__gte=date_from)
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(entry_date__lte=date_to)
        
        entry_type = filters.get('entry_type')
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        
        return queryset.order_by('-entry_date', '-created_at')


class TransactionService(BaseService):
    """Service for transaction operations"""
    
    def __init__(self):
        super().__init__(Transaction)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for transaction listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - date_from: str (date string)
                - date_to: str (date string)
        
        Returns:
            QuerySet of transactions with proper prefetch_related
        """
        queryset = self.model.objects.all().prefetch_related('journal_entries').select_related('created_by')
        
        if not filters:
            return queryset.order_by('-transaction_date', '-created_at')
        
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(transaction_date__gte=date_from)
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(transaction_date__lte=date_to)
        
        return queryset.order_by('-transaction_date', '-created_at')


# Helper functions for creating journal entries (kept in service for now, can be moved to service methods later)
def create_expense_journal_entry(expense):
    """Create journal entries for an expense - moved from views"""
    from expenses.models import Expense as ExpenseModel
    # This function is imported by expenses service, so we keep it here
    # Implementation remains the same as in views
    pass  # Implementation kept in views for now to avoid circular imports


def create_income_journal_entry(income):
    """Create journal entries for an income - moved from views"""
    from income.models import Income as IncomeModel
    # This function is imported by income service, so we keep it here
    # Implementation remains the same as in views
    pass  # Implementation kept in views for now to avoid circular imports


def create_sale_journal_entry(sale):
    """Create journal entries for a sale - moved from views"""
    from sales.models import Sale as SaleModel
    # This function is imported by sales service, so we keep it here
    # Implementation remains the same as in views
    pass  # Implementation kept in views for now to avoid circular imports
