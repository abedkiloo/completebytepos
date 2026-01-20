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


# Helper functions for creating journal entries
def create_expense_journal_entry(expense):
    """Create journal entries for an expense"""
    # Get or create expense account
    expense_account, _ = Account.objects.get_or_create(
        account_code='6000',
        defaults={
            'name': 'Operating Expenses',
            'account_type': AccountType.objects.get_or_create(
                name='expense',
                defaults={'normal_balance': 'debit'}
            )[0],
            'description': 'General operating expenses'
        }
    )
    
    # Get or create cash/bank account based on payment method
    if expense.payment_method == 'cash':
        cash_account, _ = Account.objects.get_or_create(
            account_code='1000',
            defaults={
                'name': 'Cash',
                'account_type': AccountType.objects.get_or_create(
                    name='asset',
                    defaults={'normal_balance': 'debit'}
                )[0],
                'description': 'Cash on hand'
            }
        )
        credit_account = cash_account
    else:
        bank_account, _ = Account.objects.get_or_create(
            account_code='1100',
            defaults={
                'name': 'Bank Account',
                'account_type': AccountType.objects.get_or_create(
                    name='asset',
                    defaults={'normal_balance': 'debit'}
                )[0],
                'description': 'Bank account'
            }
        )
        credit_account = bank_account
    
    # Create journal entries
    txn = Transaction.objects.create(
        transaction_date=expense.expense_date,
        description=f"Expense: {expense.description}",
        reference=expense.expense_number,
        reference_type='expense',
        reference_id=expense.id,
        created_by=expense.created_by
    )
    
    # Debit expense account
    debit_entry = JournalEntry.objects.create(
        entry_date=expense.expense_date,
        account=expense_account,
        entry_type='debit',
        amount=expense.amount,
        description=f"Expense: {expense.description}",
        reference=expense.expense_number,
        reference_type='expense',
        reference_id=expense.id,
        created_by=expense.created_by
    )
    
    # Credit cash/bank account
    credit_entry = JournalEntry.objects.create(
        entry_date=expense.expense_date,
        account=credit_account,
        entry_type='credit',
        amount=expense.amount,
        description=f"Payment for expense: {expense.description}",
        reference=expense.expense_number,
        reference_type='expense',
        reference_id=expense.id,
        created_by=expense.created_by
    )
    
    txn.journal_entries.add(debit_entry, credit_entry)
    return txn


def create_income_journal_entry(income):
    """Create journal entries for an income"""
    # Get or create income account
    income_account, _ = Account.objects.get_or_create(
        account_code='4100',
        defaults={
            'name': 'Other Income',
            'account_type': AccountType.objects.get_or_create(
                name='revenue',
                defaults={'normal_balance': 'credit'}
            )[0],
            'description': 'Other sources of income'
        }
    )
    
    # Get or create cash/bank account based on payment method
    if income.payment_method == 'cash':
        cash_account, _ = Account.objects.get_or_create(
            account_code='1000',
            defaults={
                'name': 'Cash',
                'account_type': AccountType.objects.get_or_create(
                    name='asset',
                    defaults={'normal_balance': 'debit'}
                )[0],
                'description': 'Cash on hand'
            }
        )
        debit_account = cash_account
    else:
        bank_account, _ = Account.objects.get_or_create(
            account_code='1100',
            defaults={
                'name': 'Bank Account',
                'account_type': AccountType.objects.get_or_create(
                    name='asset',
                    defaults={'normal_balance': 'debit'}
                )[0],
                'description': 'Bank account'
            }
        )
        debit_account = bank_account
    
    # Create transaction
    txn = Transaction.objects.create(
        transaction_date=income.income_date,
        description=f"Income: {income.description}",
        reference=income.income_number,
        reference_type='income',
        reference_id=income.id,
        created_by=income.created_by
    )
    
    # Debit cash/bank account
    debit_entry = JournalEntry.objects.create(
        entry_date=income.income_date,
        account=debit_account,
        entry_type='debit',
        amount=income.amount,
        description=f"Income: {income.description}",
        reference=income.income_number,
        reference_type='income',
        reference_id=income.id,
        created_by=income.created_by
    )
    
    # Credit income account
    credit_entry = JournalEntry.objects.create(
        entry_date=income.income_date,
        account=income_account,
        entry_type='credit',
        amount=income.amount,
        description=f"Income: {income.description}",
        reference=income.income_number,
        reference_type='income',
        reference_id=income.id,
        created_by=income.created_by
    )
    
    txn.journal_entries.add(debit_entry, credit_entry)
    return txn


def create_sale_journal_entry(sale):
    """Create journal entries for a sale
    
    For POS sales: Debit Cash, Credit Sales Revenue
    For Normal sales: Debit Accounts Receivable (or Cash if paid), Credit Sales Revenue
    """
    # Get or create accounts
    sales_revenue_account, _ = Account.objects.get_or_create(
        account_code='4000',
        defaults={
            'name': 'Sales Revenue',
            'account_type': AccountType.objects.get_or_create(
                name='revenue',
                defaults={'normal_balance': 'credit'}
            )[0],
            'description': 'Sales revenue'
        }
    )
    
    cash_account, _ = Account.objects.get_or_create(
        account_code='1000',
        defaults={
            'name': 'Cash',
            'account_type': AccountType.objects.get_or_create(
                name='asset',
                defaults={'normal_balance': 'debit'}
            )[0],
            'description': 'Cash on hand'
        }
    )
    
    accounts_receivable_account, _ = Account.objects.get_or_create(
        account_code='1200',
        defaults={
            'name': 'Accounts Receivable',
            'account_type': AccountType.objects.get_or_create(
                name='asset',
                defaults={'normal_balance': 'debit'}
            )[0],
            'description': 'Accounts receivable from customers'
        }
    )
    
    # Get or create customer prepaid/wallet account (liability - we owe customers this money)
    customer_prepaid_account, _ = Account.objects.get_or_create(
        account_code='2100',
        defaults={
            'name': 'Customer Prepaid/Wallet',
            'account_type': AccountType.objects.get_or_create(
                name='liability',
                defaults={'normal_balance': 'credit'}
            )[0],
            'description': 'Customer wallet balances and prepaid amounts'
        }
    )
    
    # Create transaction
    txn = Transaction.objects.create(
        transaction_date=sale.created_at.date(),
        description=f"Sale: {sale.sale_number}",
        reference=sale.sale_number,
        reference_type='sale',
        reference_id=sale.id,
        created_by=sale.cashier
    )
    
    entries = []
    
    # Determine sale type and payment amount
    sale_type = getattr(sale, 'sale_type', 'pos')  # Default to 'pos' for backward compatibility
    amount_paid = sale.amount_paid or Decimal('0')
    total = sale.total  # Total includes delivery_cost
    balance = total - amount_paid
    overpayment = amount_paid - total if amount_paid > total else Decimal('0')
    
    # Validate: amount_paid should not exceed total by an unreasonable amount
    # (allowing small rounding differences)
    if overpayment > Decimal('1000'):
        raise ValueError(
            f"Overpayment amount ({overpayment}) exceeds reasonable limit. "
            f"Amount paid: {amount_paid}, Total: {total}"
        )
    
    # Handle payment entries for both POS and normal sales
    # POS sales can also have partial payments (e.g., customer paid 600 on 1000 sale)
    if amount_paid > 0:
        # Debit Cash for amount paid
        cash_entry = JournalEntry.objects.create(
            entry_date=sale.created_at.date(),
            account=cash_account,
            entry_type='debit',
            amount=amount_paid,
            description=f"{'POS Sale' if sale_type == 'pos' else 'Sale'} payment: {sale.sale_number}",
            reference=sale.sale_number,
            reference_type='sale',
            reference_id=sale.id,
            created_by=sale.cashier
        )
        entries.append(cash_entry)
    
    if balance > 0:
        # Debit Accounts Receivable for unpaid balance
        # This applies to both POS sales with partial payment and normal sales on credit
        ar_entry = JournalEntry.objects.create(
            entry_date=sale.created_at.date(),
            account=accounts_receivable_account,
            entry_type='debit',
            amount=balance,
            description=f"{'POS Sale' if sale_type == 'pos' else 'Sale'} on credit: {sale.sale_number}",
            reference=sale.sale_number,
            reference_type='sale',
            reference_id=sale.id,
            created_by=sale.cashier
        )
        entries.append(ar_entry)
    
    # Credit sales revenue (always)
    credit_entry = JournalEntry.objects.create(
        entry_date=sale.created_at.date(),
        account=sales_revenue_account,
        entry_type='credit',
        amount=total,
        description=f"Sale: {sale.sale_number}",
        reference=sale.sale_number,
        reference_type='sale',
        reference_id=sale.id,
        created_by=sale.cashier
    )
    entries.append(credit_entry)
    
    if overpayment > 0:
        # Credit Customer Prepaid/Wallet for overpayment
        # This represents money we owe the customer (added to their wallet)
        prepaid_entry = JournalEntry.objects.create(
            entry_date=sale.created_at.date(),
            account=customer_prepaid_account,
            entry_type='credit',
            amount=overpayment,
            description=f"Overpayment from sale added to wallet: {sale.sale_number}",
            reference=sale.sale_number,
            reference_type='sale',
            reference_id=sale.id,
            created_by=sale.cashier
        )
        entries.append(prepaid_entry)
    
    txn.journal_entries.add(*entries)
    return txn
