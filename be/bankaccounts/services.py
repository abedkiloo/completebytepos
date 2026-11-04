"""
Query and balance helpers for bank accounts and transactions.

Public entry points:
    - ``BankAccountService.build_queryset`` / ``update_balance``
    - ``BankTransactionService.build_queryset``

Side effects: ``update_balance`` delegates to model ``BankAccount.update_balance``
(DB write on the account row). Listing methods are read-only.
"""
from typing import Optional, List, Dict, Any
from django.db.models import Q, Count, QuerySet
from .models import BankAccount, BankTransaction
from services.base import BaseService


class BankAccountService(BaseService):
    """
    Filtered listings and balance refresh for ``BankAccount``.

    Attributes:
        model: Bound to ``BankAccount``.
    """

    def __init__(self):
        super().__init__(BankAccount)

    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build bank account queryset with optional active filter.

        Args:
            filters: Optional dict. Supported keys:
                is_active: bool or ``'true'``/``'false'`` string.

        Returns:
            ``QuerySet`` annotated with ``transaction_count``, ordered by
            bank name then account name. No pagination cap applied here.
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
        """
        Recalculate and persist operational balance for one account.

        Args:
            account: ``BankAccount`` instance to refresh.

        Returns:
            Same instance with updated ``current_balance`` (refreshed from DB
            after model save).

        Side effects:
            Writes ``current_balance`` via ``BankAccount.update_balance``.
        """
        account.update_balance()
        return account


class BankTransactionService(BaseService):
    """
    Filtered transaction listings with related account and user.

    Attributes:
        model: Bound to ``BankTransaction``.
    """

    def __init__(self):
        super().__init__(BankTransaction)

    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build transaction queryset with account and date filters.

        Args:
            filters: Optional dict. Supported keys:
                account: bank account PK (int as string); invalid → empty queryset.
                date_from / date_to: inclusive ``transaction_date`` bounds.

        Returns:
            ``QuerySet`` with ``select_related('bank_account', 'created_by')``,
            ordered by ``-transaction_date``, ``-created_at``.
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
