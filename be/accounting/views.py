from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Q, F
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime, date
from decimal import Decimal
from utils.pdf_generator import create_balance_sheet_pdf, create_income_statement_pdf, create_trial_balance_pdf
from .models import AccountType, Account, JournalEntry, Transaction
from .serializers import (
    AccountTypeSerializer, AccountSerializer, AccountListSerializer,
    JournalEntrySerializer, TransactionSerializer,
    BalanceSheetSerializer, IncomeStatementSerializer, TrialBalanceSerializer
)
from .services import AccountTypeService, AccountService, JournalEntryService, TransactionService
from expenses.models import Expense
from sales.models import Sale


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
    
    if sale_type == 'pos':
        # POS sale: Full payment received immediately
        # Debit Cash
        debit_entry = JournalEntry.objects.create(
            entry_date=sale.created_at.date(),
            account=cash_account,
            entry_type='debit',
            amount=total,
            description=f"POS Sale: {sale.sale_number}",
            reference=sale.sale_number,
            reference_type='sale',
            reference_id=sale.id,
            created_by=sale.cashier
        )
        entries.append(debit_entry)
    else:
        # Normal sale: May have partial or no payment
        if amount_paid > 0:
            # Debit Cash for amount paid
            cash_entry = JournalEntry.objects.create(
                entry_date=sale.created_at.date(),
                account=cash_account,
                entry_type='debit',
                amount=amount_paid,
                description=f"Sale payment: {sale.sale_number}",
                reference=sale.sale_number,
                reference_type='sale',
                reference_id=sale.id,
                created_by=sale.cashier
            )
            entries.append(cash_entry)
        
        if balance > 0:
            # Debit Accounts Receivable for balance
            ar_entry = JournalEntry.objects.create(
                entry_date=sale.created_at.date(),
                account=accounts_receivable_account,
                entry_type='debit',
                amount=balance,
                description=f"Sale on credit: {sale.sale_number}",
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
    
    txn.journal_entries.add(*entries)
    return txn


def create_invoice_journal_entry(invoice):
    """Create journal entries for an invoice (if not already created from sale)
    
    This is used when invoices are created manually or from existing sales.
    If the invoice has a sale, the sale journal entry should have already
    handled the accounting. This function handles manual invoice creation.
    """
    # Only create entries if invoice was created manually (no sale)
    if invoice.sale:
        # Sale journal entry should have already handled this
        return None
    
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
    
    # Create transaction
    txn = Transaction.objects.create(
        transaction_date=invoice.issued_date or timezone.now().date(),
        description=f"Invoice: {invoice.invoice_number}",
        reference=invoice.invoice_number,
        reference_type='invoice',
        reference_id=invoice.id,
        created_by=invoice.created_by
    )
    
    # Debit Accounts Receivable
    debit_entry = JournalEntry.objects.create(
        entry_date=invoice.issued_date or timezone.now().date(),
        account=accounts_receivable_account,
        entry_type='debit',
        amount=invoice.total,
        description=f"Invoice: {invoice.invoice_number}",
        reference=invoice.invoice_number,
        reference_type='invoice',
        reference_id=invoice.id,
        created_by=invoice.created_by
    )
    
    # Credit Sales Revenue
    credit_entry = JournalEntry.objects.create(
        entry_date=invoice.issued_date or timezone.now().date(),
        account=sales_revenue_account,
        entry_type='credit',
        amount=invoice.total,
        description=f"Invoice: {invoice.invoice_number}",
        reference=invoice.invoice_number,
        reference_type='invoice',
        reference_id=invoice.id,
        created_by=invoice.created_by
    )
    
    txn.journal_entries.add(debit_entry, credit_entry)
    return txn


def create_payment_journal_entry(payment):
    """Create journal entries for a payment against an invoice
    
    Debit Cash/Bank (based on payment method)
    Credit Accounts Receivable
    """
    invoice = payment.invoice
    
    # Get or create accounts
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
    
    # Get cash/bank account based on payment method
    if payment.payment_method == 'cash':
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
        # For bank transfers, M-PESA, card, etc., use bank account
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
        transaction_date=payment.payment_date,
        description=f"Payment for Invoice: {invoice.invoice_number}",
        reference=payment.reference or invoice.invoice_number,
        reference_type='payment',
        reference_id=payment.id,
        created_by=payment.recorded_by
    )
    
    # Debit Cash/Bank
    debit_entry = JournalEntry.objects.create(
        entry_date=payment.payment_date,
        account=debit_account,
        entry_type='debit',
        amount=payment.amount,
        description=f"Payment for Invoice: {invoice.invoice_number}",
        reference=payment.reference or invoice.invoice_number,
        reference_type='payment',
        reference_id=payment.id,
        created_by=payment.recorded_by
    )
    
    # Credit Accounts Receivable
    credit_entry = JournalEntry.objects.create(
        entry_date=payment.payment_date,
        account=accounts_receivable_account,
        entry_type='credit',
        amount=payment.amount,
        description=f"Payment received for Invoice: {invoice.invoice_number}",
        reference=payment.reference or invoice.invoice_number,
        reference_type='payment',
        reference_id=payment.id,
        created_by=payment.recorded_by
    )
    
    txn.journal_entries.add(debit_entry, credit_entry)
    return txn


class AccountTypeViewSet(viewsets.ModelViewSet):
    queryset = AccountType.objects.all()
    serializer_class = AccountTypeSerializer
    ordering = ['name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.account_type_service = AccountTypeService()
    
    def get_queryset(self):
        """Get queryset using service layer"""
        return self.account_type_service.build_queryset()


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().select_related('account_type', 'parent')
    serializer_class = AccountSerializer
    ordering = ['account_code']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.account_service = AccountService()

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['account_type', 'is_active']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.account_service.build_queryset(filters)

    @action(detail=True, methods=['post'])
    def update_balance(self, request, pk=None):
        """Manually update account balance - thin view, business logic in service"""
        account = self.get_object()
        updated_account = self.account_service.update_balance(account)
        serializer = self.get_serializer(updated_account)
        return Response(serializer.data)


class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all().select_related('account', 'created_by')
    serializer_class = JournalEntrySerializer
    ordering = ['-entry_date', '-created_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal_entry_service = JournalEntryService()

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['account', 'date_from', 'date_to', 'entry_type']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.journal_entry_service.build_queryset(filters)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().prefetch_related('journal_entries').select_related('created_by')
    serializer_class = TransactionSerializer
    ordering = ['-transaction_date', '-created_at']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction_service = TransactionService()

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['date_from', 'date_to']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.transaction_service.build_queryset(filters)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AccountingReportViewSet(viewsets.ViewSet):
    """Accounting reports"""
    
    @action(detail=False, methods=['get'])
    def balance_sheet(self, request):
        """Generate balance sheet"""
        as_of_date = request.query_params.get('date', None)
        if as_of_date:
            as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
        else:
            as_of_date = date.today()
        
        # Get accounts up to the date
        entries_until_date = JournalEntry.objects.filter(entry_date__lte=as_of_date)
        
        # Assets
        asset_type = AccountType.objects.get(name='asset')
        assets = {}
        asset_accounts = Account.objects.filter(account_type=asset_type, is_active=True)
        total_assets = Decimal('0.00')
        
        for account in asset_accounts:
            debit_total = entries_until_date.filter(
                account=account, entry_type='debit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            credit_total = entries_until_date.filter(
                account=account, entry_type='credit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            balance = account.opening_balance + debit_total - credit_total
            if balance != 0:
                assets[account.name] = {
                    'account_code': account.account_code,
                    'balance': float(balance)
                }
                total_assets += balance
        
        # Liabilities
        try:
            liability_type = AccountType.objects.get(name='liability')
        except AccountType.DoesNotExist:
            liability_type = None
        
        liabilities = {}
        liability_accounts = Account.objects.filter(account_type=liability_type, is_active=True) if liability_type else []
        total_liabilities = Decimal('0.00')
        
        for account in liability_accounts:
            debit_total = entries_until_date.filter(
                account=account, entry_type='debit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            credit_total = entries_until_date.filter(
                account=account, entry_type='credit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            balance = account.opening_balance + credit_total - debit_total
            if balance != 0:
                liabilities[account.name] = {
                    'account_code': account.account_code,
                    'balance': float(balance)
                }
                total_liabilities += balance
        
        # Equity
        try:
            equity_type = AccountType.objects.get(name='equity')
        except AccountType.DoesNotExist:
            equity_type = None
        
        equity = {}
        equity_accounts = Account.objects.filter(account_type=equity_type, is_active=True) if equity_type else []
        total_equity = Decimal('0.00')
        
        for account in equity_accounts:
            debit_total = entries_until_date.filter(
                account=account, entry_type='debit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            credit_total = entries_until_date.filter(
                account=account, entry_type='credit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            balance = account.opening_balance + credit_total - debit_total
            if balance != 0:
                equity[account.name] = {
                    'account_code': account.account_code,
                    'balance': float(balance)
                }
                total_equity += balance
        
        # Calculate retained earnings (Revenue - Expenses)
        try:
            revenue_type = AccountType.objects.get(name='revenue')
            expense_type = AccountType.objects.get(name='expense')
        except AccountType.DoesNotExist:
            revenue_type = None
            expense_type = None
        
        revenue_total = Decimal('0.00')
        if revenue_type:
            for account in Account.objects.filter(account_type=revenue_type, is_active=True):
                credit_total = entries_until_date.filter(
                    account=account, entry_type='credit'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                revenue_total += credit_total
        
        expense_total = Decimal('0.00')
        if expense_type:
            for account in Account.objects.filter(account_type=expense_type, is_active=True):
                debit_total = entries_until_date.filter(
                    account=account, entry_type='debit'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                expense_total += debit_total
        
        net_income = revenue_total - expense_total
        
        # Add retained earnings to equity
        if net_income != 0:
            equity['Retained Earnings'] = {
                'account_code': '3000',
                'balance': float(net_income)
            }
            total_equity += net_income
        
        data = {
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'total_assets': float(total_assets),
            'total_liabilities': float(total_liabilities),
            'total_equity': float(total_equity),
            'date': as_of_date.isoformat(),
        }
        
        serializer = BalanceSheetSerializer(data)
        
        # Check if PDF download is requested
        if request.query_params.get('format') == 'pdf':
            pdf_buffer = create_balance_sheet_pdf(serializer.data)
            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            filename = f"BalanceSheet_{data['date']}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def income_statement(self, request):
        """Generate income statement (Profit & Loss)"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        if not date_from:
            # Default to current month
            today = date.today()
            date_from = date(today.year, today.month, 1)
        else:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        
        if not date_to:
            date_to = date.today()
        else:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        entries_in_period = JournalEntry.objects.filter(
            entry_date__gte=date_from,
            entry_date__lte=date_to
        )
        
        # Revenue
        try:
            revenue_type = AccountType.objects.get(name='revenue')
        except AccountType.DoesNotExist:
            return Response(
                {'error': 'Account types not initialized. Please set up chart of accounts first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        revenue = {}
        revenue_accounts = Account.objects.filter(account_type=revenue_type, is_active=True)
        total_revenue = Decimal('0.00')
        
        for account in revenue_accounts:
            credit_total = entries_in_period.filter(
                account=account, entry_type='credit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            if credit_total > 0:
                revenue[account.name] = {
                    'account_code': account.account_code,
                    'amount': float(credit_total)
                }
                total_revenue += credit_total
        
        # Expenses
        try:
            expense_type = AccountType.objects.get(name='expense')
        except AccountType.DoesNotExist:
            return Response(
                {'error': 'Account types not initialized. Please set up chart of accounts first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        expenses = {}
        expense_accounts = Account.objects.filter(account_type=expense_type, is_active=True)
        total_expenses = Decimal('0.00')
        
        for account in expense_accounts:
            debit_total = entries_in_period.filter(
                account=account, entry_type='debit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            if debit_total > 0:
                expenses[account.name] = {
                    'account_code': account.account_code,
                    'amount': float(debit_total)
                }
                total_expenses += debit_total
        
        net_income = total_revenue - total_expenses
        
        data = {
            'revenue': revenue,
            'expenses': expenses,
            'total_revenue': float(total_revenue),
            'total_expenses': float(total_expenses),
            'net_income': float(net_income),
            'period_start': date_from.isoformat(),
            'period_end': date_to.isoformat(),
        }
        
        serializer = IncomeStatementSerializer(data)
        
        # Check if PDF download is requested
        if request.query_params.get('format') == 'pdf':
            pdf_buffer = create_income_statement_pdf(serializer.data)
            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            filename = f"IncomeStatement_{data['period_start']}_to_{data['period_end']}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trial_balance(self, request):
        """Generate trial balance"""
        as_of_date = request.query_params.get('date', None)
        if as_of_date:
            as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
        else:
            as_of_date = date.today()
        
        entries_until_date = JournalEntry.objects.filter(entry_date__lte=as_of_date)
        
        accounts_data = []
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        
        for account in Account.objects.filter(is_active=True).order_by('account_code'):
            debit_total = entries_until_date.filter(
                account=account, entry_type='debit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            credit_total = entries_until_date.filter(
                account=account, entry_type='credit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            if account.account_type.normal_balance == 'debit':
                balance = account.opening_balance + debit_total - credit_total
                debit_balance = balance if balance > 0 else Decimal('0.00')
                credit_balance = -balance if balance < 0 else Decimal('0.00')
            else:
                balance = account.opening_balance + credit_total - debit_total
                debit_balance = -balance if balance < 0 else Decimal('0.00')
                credit_balance = balance if balance > 0 else Decimal('0.00')
            
            if debit_balance != 0 or credit_balance != 0:
                accounts_data.append({
                    'account_code': account.account_code,
                    'account_name': account.name,
                    'account_type': account.account_type.name,
                    'debit': float(debit_balance),
                    'credit': float(credit_balance),
                    'balance': float(balance),
                })
                total_debits += debit_balance
                total_credits += credit_balance
        
        data = {
            'accounts': accounts_data,
            'total_debits': float(total_debits),
            'total_credits': float(total_credits),
            'date': as_of_date.isoformat(),
        }
        
        serializer = TrialBalanceSerializer(data)
        
        # Check if PDF download is requested
        if request.query_params.get('format') == 'pdf':
            pdf_buffer = create_trial_balance_pdf(serializer.data)
            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            filename = f"TrialBalance_{data['date']}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def general_ledger(self, request):
        """Generate general ledger for an account"""
        account_id = request.query_params.get('account_id', None)
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        if not account_id:
            return Response(
                {'error': 'account_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        entries = JournalEntry.objects.filter(account=account)
        
        if date_from:
            entries = entries.filter(entry_date__gte=date_from)
        if date_to:
            entries = entries.filter(entry_date__lte=date_to)
        
        entries = entries.order_by('entry_date', 'created_at')
        
        running_balance = account.opening_balance
        ledger_entries = []
        
        for entry in entries:
            if account.account_type.normal_balance == 'debit':
                if entry.entry_type == 'debit':
                    running_balance += entry.amount
                else:
                    running_balance -= entry.amount
            else:
                if entry.entry_type == 'credit':
                    running_balance += entry.amount
                else:
                    running_balance -= entry.amount
            
            ledger_entries.append({
                'entry_number': entry.entry_number,
                'entry_date': entry.entry_date.isoformat(),
                'entry_type': entry.entry_type,
                'amount': float(entry.amount),
                'description': entry.description,
                'reference': entry.reference,
                'running_balance': float(running_balance),
            })
        
        return Response({
            'account': {
                'id': account.id,
                'account_code': account.account_code,
                'name': account.name,
                'account_type': account.account_type.name,
                'opening_balance': float(account.opening_balance),
            },
            'entries': ledger_entries,
            'closing_balance': float(running_balance),
        })
    
    @action(detail=False, methods=['get'])
    def cash_flow(self, request):
        """Generate cash flow statement"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        if not date_from:
            # Default to current month
            today = date.today()
            date_from = date(today.year, today.month, 1)
        else:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        
        if not date_to:
            date_to = date.today()
        else:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        entries_in_period = JournalEntry.objects.filter(
            entry_date__gte=date_from,
            entry_date__lte=date_to
        )
        
        # Operating Activities
        # Cash from sales
        try:
            sales_account = Account.objects.get(account_code='4000')
            cash_from_sales = entries_in_period.filter(
                account=sales_account,
                entry_type='credit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        except Account.DoesNotExist:
            cash_from_sales = Decimal('0.00')
        
        # Cash paid for expenses
        try:
            expense_account = Account.objects.get(account_code='6000')
            cash_paid_expenses = entries_in_period.filter(
                account=expense_account,
                entry_type='debit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        except Account.DoesNotExist:
            cash_paid_expenses = Decimal('0.00')
        
        # Investing Activities (placeholder - can be extended)
        investing_activities = Decimal('0.00')
        
        # Financing Activities (placeholder - can be extended)
        financing_activities = Decimal('0.00')
        
        # Net cash flow
        net_cash_flow = cash_from_sales - cash_paid_expenses + investing_activities + financing_activities
        
        # Beginning and ending cash
        try:
            cash_account = Account.objects.get(account_code='1000')
            beginning_cash = cash_account.opening_balance
            ending_cash = beginning_cash + net_cash_flow
        except Account.DoesNotExist:
            beginning_cash = Decimal('0.00')
            ending_cash = net_cash_flow
        
        return Response({
            'period_start': date_from.isoformat(),
            'period_end': date_to.isoformat(),
            'operating_activities': {
                'cash_from_sales': float(cash_from_sales),
                'cash_paid_expenses': float(cash_paid_expenses),
                'net_operating': float(cash_from_sales - cash_paid_expenses),
            },
            'investing_activities': {
                'total': float(investing_activities),
            },
            'financing_activities': {
                'total': float(financing_activities),
            },
            'net_cash_flow': float(net_cash_flow),
            'beginning_cash': float(beginning_cash),
            'ending_cash': float(ending_cash),
        })
    
    @action(detail=False, methods=['get'])
    def account_statement(self, request):
        """Generate account statement for an accounting account (works like general ledger but formatted as statement)"""
        account_id = request.query_params.get('account_id', None)
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        if not account_id:
            return Response(
                {'error': 'account_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        entries = JournalEntry.objects.filter(account=account)
        
        if date_from:
            entries = entries.filter(entry_date__gte=date_from)
        if date_to:
            entries = entries.filter(entry_date__lte=date_to)
        
        entries = entries.order_by('entry_date', 'created_at')
        
        running_balance = account.opening_balance
        statement_entries = []
        
        for entry in entries:
            if account.account_type.normal_balance == 'debit':
                if entry.entry_type == 'debit':
                    running_balance += entry.amount
                else:
                    running_balance -= entry.amount
            else:  # credit normal balance
                if entry.entry_type == 'credit':
                    running_balance += entry.amount
                else:
                    running_balance -= entry.amount
            
            statement_entries.append({
                'entry_number': entry.entry_number,
                'entry_date': entry.entry_date.isoformat(),
                'entry_type': entry.entry_type,
                'description': entry.description,
                'reference': entry.reference,
                'amount': float(entry.amount),
                'balance': float(running_balance),
            })
        
        return Response({
            'account': {
                'id': account.id,
                'account_code': account.account_code,
                'account_name': account.name,
                'account_type': account.account_type.name,
                'opening_balance': float(account.opening_balance),
                'currency': 'KES',  # Default currency
            },
            'period_start': date_from or account.created_at.date().isoformat(),
            'period_end': date_to or date.today().isoformat(),
            'entries': statement_entries,
            'closing_balance': float(running_balance),
        })
