from django.core.management.base import BaseCommand
from accounting.models import AccountType, Account
from decimal import Decimal


class Command(BaseCommand):
    help = 'Initialize basic chart of accounts'

    def handle(self, *args, **options):
        self.stdout.write('Initializing chart of accounts...')
        
        # Create Account Types
        account_types = [
            {'name': 'asset', 'description': 'Assets', 'normal_balance': 'debit'},
            {'name': 'liability', 'description': 'Liabilities', 'normal_balance': 'credit'},
            {'name': 'equity', 'description': 'Equity', 'normal_balance': 'credit'},
            {'name': 'revenue', 'description': 'Revenue', 'normal_balance': 'credit'},
            {'name': 'expense', 'description': 'Expenses', 'normal_balance': 'debit'},
        ]
        
        for at_data in account_types:
            account_type, created = AccountType.objects.get_or_create(
                name=at_data['name'],
                defaults=at_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created account type: {account_type.name}'))
            else:
                self.stdout.write(f'Account type already exists: {account_type.name}')
        
        # Create Basic Accounts
        accounts = [
            # Assets (1000-1999)
            {'code': '1000', 'name': 'Cash', 'type': 'asset', 'description': 'Cash on hand'},
            {'code': '1100', 'name': 'Bank Account', 'type': 'asset', 'description': 'Bank account'},
            {'code': '1200', 'name': 'Accounts Receivable', 'type': 'asset', 'description': 'Amounts owed by customers'},
            {'code': '1300', 'name': 'Inventory', 'type': 'asset', 'description': 'Product inventory'},
            
            # Liabilities (2000-2999)
            {'code': '2000', 'name': 'Accounts Payable', 'type': 'liability', 'description': 'Amounts owed to suppliers'},
            {'code': '2100', 'name': 'Loans Payable', 'type': 'liability', 'description': 'Outstanding loans'},
            
            # Equity (3000-3999)
            {'code': '3000', 'name': 'Retained Earnings', 'type': 'equity', 'description': 'Accumulated profits'},
            {'code': '3100', 'name': 'Owner\'s Equity', 'type': 'equity', 'description': 'Owner\'s capital'},
            
            # Revenue (4000-4999)
            {'code': '4000', 'name': 'Sales Revenue', 'type': 'revenue', 'description': 'Revenue from sales'},
            {'code': '4100', 'name': 'Other Income', 'type': 'revenue', 'description': 'Other sources of income'},
            
            # Expenses (5000-6999)
            {'code': '5000', 'name': 'Cost of Goods Sold', 'type': 'expense', 'description': 'Cost of products sold'},
            {'code': '6000', 'name': 'Operating Expenses', 'type': 'expense', 'description': 'General operating expenses'},
            {'code': '6100', 'name': 'Rent Expense', 'type': 'expense', 'description': 'Rent payments'},
            {'code': '6200', 'name': 'Utilities Expense', 'type': 'expense', 'description': 'Utility bills'},
            {'code': '6300', 'name': 'Salaries Expense', 'type': 'expense', 'description': 'Employee salaries'},
        ]
        
        for acc_data in accounts:
            account_type = AccountType.objects.get(name=acc_data['type'])
            account, created = Account.objects.get_or_create(
                account_code=acc_data['code'],
                defaults={
                    'name': acc_data['name'],
                    'account_type': account_type,
                    'description': acc_data['description'],
                    'opening_balance': Decimal('0.00'),
                    'current_balance': Decimal('0.00'),
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created account: {account.account_code} - {account.name}'))
            else:
                self.stdout.write(f'Account already exists: {account.account_code} - {account.name}')
        
        self.stdout.write(self.style.SUCCESS('\nChart of accounts initialized successfully!'))

