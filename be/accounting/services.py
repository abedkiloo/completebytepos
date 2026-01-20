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
    
    # Get wallet amount used from wallet transactions
    # Wallet transactions with transaction_type='debit' and source_type='payment' represent wallet usage
    wallet_amount_used = Decimal('0')
    try:
        from sales.models import CustomerWalletTransaction
        from django.utils import timezone
        from datetime import timedelta
        
        # First, try to find wallet transactions by sale reference (preferred method)
        wallet_debits = CustomerWalletTransaction.objects.filter(
            sale=sale,
            transaction_type='debit',
            source_type='payment'
        ).aggregate(total=Sum('amount'))['total']
        
        # If no wallet transactions found by sale reference, try to find by customer, cashier and time window
        # This handles the case where wallet transactions are created before the sale reference is set
        # We match by: same customer, same cashier, same time window, debit type, payment source, no sale reference yet
        if not wallet_debits and sale.cashier:
            # First, try to get customer from sale's invoice (if invoice exists)
            customer = None
            try:
                # Check if sale has an invoice with a customer
                invoice = sale.invoices.first()  # Get first invoice if any
                if invoice and invoice.customer:
                    customer = invoice.customer
            except Exception:
                pass
            
            # If we couldn't get customer from invoice, try to infer from wallet transactions
            # Look for wallet transactions created within 5 minutes before and 1 minute after sale creation
            # that were created by the same user (cashier) and match the transaction characteristics
            time_window_start = sale.created_at - timedelta(minutes=5)
            time_window_end = sale.created_at + timedelta(minutes=1)
            
            # Find all potential wallet transactions matching cashier and time window
            potential_wallet_txns = CustomerWalletTransaction.objects.filter(
                sale__isnull=True,  # Not yet linked to a sale
                transaction_type='debit',
                source_type='payment',
                created_by=sale.cashier,  # Same cashier
                created_at__gte=time_window_start,
                created_at__lte=time_window_end
            )
            
            # If we have a customer from invoice, filter by that customer
            if customer:
                matching_wallet_txns = potential_wallet_txns.filter(customer=customer)
            else:
                # If no customer from invoice, check if all potential transactions belong to the same customer
                # This prevents mixing transactions from different customers
                distinct_customers = potential_wallet_txns.values_list('customer', flat=True).distinct()
                
                if len(distinct_customers) == 1:
                    # All transactions belong to the same customer - safe to use
                    customer_id = distinct_customers[0]
                    if customer_id:  # customer_id could be None, skip if so
                        matching_wallet_txns = potential_wallet_txns.filter(customer_id=customer_id)
                    else:
                        # No customer on transactions - can't safely match
                        matching_wallet_txns = CustomerWalletTransaction.objects.none()
                elif len(distinct_customers) > 1:
                    # Multiple customers in time window - too ambiguous, don't match
                    # This prevents incorrect matching when multiple sales happen rapidly
                    matching_wallet_txns = CustomerWalletTransaction.objects.none()
                else:
                    # No transactions found
                    matching_wallet_txns = CustomerWalletTransaction.objects.none()
            
            # If we find matching transactions, use them
            if matching_wallet_txns.exists():
                # Sum all matching transactions (in case there are multiple for the same customer)
                wallet_debits = matching_wallet_txns.aggregate(total=Sum('amount'))['total']
                
                # If we found wallet transactions, link them to this sale for future reference
                # This ensures the sale reference is set even if views.py doesn't do it
                if wallet_debits:
                    matching_wallet_txns.update(sale=sale)
        
        wallet_amount_used = wallet_debits or Decimal('0')
    except Exception as e:
        # If wallet transactions can't be accessed, assume 0
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error retrieving wallet transactions for sale {sale.sale_number}: {e}")
        wallet_amount_used = Decimal('0')
    
    # Calculate total payment (cash + wallet)
    total_payment = amount_paid + wallet_amount_used
    
    # Calculate balance (unpaid amount after cash and wallet)
    balance = total - total_payment
    overpayment = total_payment - total if total_payment > total else Decimal('0')
    
    # Validate: total_payment should not exceed total by an unreasonable amount
    # (allowing small rounding differences)
    if overpayment > Decimal('1000'):
        raise ValueError(
            f"Overpayment amount ({overpayment}) exceeds reasonable limit. "
            f"Amount paid: {amount_paid}, Wallet used: {wallet_amount_used}, Total: {total}"
        )
    
    # Handle payment entries for both POS and normal sales
    # Debit Cash for cash/mpesa payment
    if amount_paid > 0:
        cash_entry = JournalEntry.objects.create(
            entry_date=sale.created_at.date(),
            account=cash_account,
            entry_type='debit',
            amount=amount_paid,
            description=f"{'POS Sale' if sale_type == 'pos' else 'Sale'} payment (cash/mpesa): {sale.sale_number}",
            reference=sale.sale_number,
            reference_type='sale',
            reference_id=sale.id,
            created_by=sale.cashier
        )
        entries.append(cash_entry)
    
    # Debit Customer Prepaid/Wallet for wallet amount used
    # Since Customer Prepaid/Wallet is a liability (credit normal balance),
    # debiting it reduces the liability (customer's wallet balance decreases)
    if wallet_amount_used > 0:
        wallet_entry = JournalEntry.objects.create(
            entry_date=sale.created_at.date(),
            account=customer_prepaid_account,
            entry_type='debit',
            amount=wallet_amount_used,
            description=f"{'POS Sale' if sale_type == 'pos' else 'Sale'} payment (wallet): {sale.sale_number}",
            reference=sale.sale_number,
            reference_type='sale',
            reference_id=sale.id,
            created_by=sale.cashier
        )
        entries.append(wallet_entry)
    
    # Debit Accounts Receivable for unpaid balance (only if there's an actual unpaid amount)
    if balance > 0:
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
