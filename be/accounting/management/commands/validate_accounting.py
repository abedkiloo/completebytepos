"""
Management command to validate accounting entries and ensure everything balances
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum
from accounting.models import Transaction, JournalEntry, Account
from decimal import Decimal


class Command(BaseCommand):
    help = 'Validate accounting entries and ensure all transactions balance'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('ACCOUNTING VALIDATION REPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Check all transactions balance
        transactions = Transaction.objects.all()
        unbalanced = []
        total_debits = Decimal('0')
        total_credits = Decimal('0')
        
        for txn in transactions:
            entries = txn.journal_entries.all()
            debit_total = sum(e.amount for e in entries if e.entry_type == 'debit')
            credit_total = sum(e.amount for e in entries if e.entry_type == 'credit')
            
            total_debits += debit_total
            total_credits += credit_total
            
            if debit_total != credit_total:
                unbalanced.append({
                    'transaction': txn,
                    'debits': debit_total,
                    'credits': credit_total,
                    'difference': abs(debit_total - credit_total)
                })
        
        # Report results
        self.stdout.write(f'\n📊 Transaction Balance Check:')
        self.stdout.write(f'  Total Transactions: {transactions.count()}')
        self.stdout.write(f'  Unbalanced Transactions: {len(unbalanced)}')
        self.stdout.write(f'  Total Debits: {total_debits}')
        self.stdout.write(f'  Total Credits: {total_credits}')
        self.stdout.write(f'  Overall Balance: {"✓ BALANCED" if total_debits == total_credits else "✗ UNBALANCED"}')
        
        if unbalanced:
            self.stdout.write(self.style.ERROR('\n⚠️  Unbalanced Transactions:'))
            for item in unbalanced[:10]:  # Show first 10
                self.stdout.write(self.style.ERROR(
                    f'  {item["transaction"].transaction_number}: '
                    f'Debits={item["debits"]}, Credits={item["credits"]}, '
                    f'Difference={item["difference"]}'
                ))
        
        # Check account balances
        self.stdout.write(f'\n📈 Account Balance Summary:')
        accounts = Account.objects.filter(is_active=True)
        for account in accounts:
            account.update_balance()
            self.stdout.write(
                f'  {account.account_code} - {account.name}: '
                f'{account.current_balance}'
            )
        
        # Trial balance check
        self.stdout.write(f'\n⚖️  Trial Balance Check:')
        all_debits = Decimal('0')
        all_credits = Decimal('0')
        
        for account in accounts:
            debit_total = JournalEntry.objects.filter(
                account=account, entry_type='debit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            credit_total = JournalEntry.objects.filter(
                account=account, entry_type='credit'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            if account.account_type.normal_balance == 'debit':
                balance = account.opening_balance + debit_total - credit_total
                if balance > 0:
                    all_debits += balance
                else:
                    all_credits += abs(balance)
            else:
                balance = account.opening_balance + credit_total - debit_total
                if balance > 0:
                    all_credits += balance
                else:
                    all_debits += abs(balance)
        
        self.stdout.write(f'  Total Debit Balances: {all_debits}')
        self.stdout.write(f'  Total Credit Balances: {all_credits}')
        self.stdout.write(f'  Trial Balance: {"✓ BALANCED" if all_debits == all_credits else "✗ UNBALANCED"}')
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('VALIDATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
