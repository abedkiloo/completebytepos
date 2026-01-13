"""
Management command to set up a new organization with initial data
Run this after creating a superuser to populate the system with default data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from settings.models import Branch


class Command(BaseCommand):
    help = 'Set up a new organization with initial data (modules, accounts, categories, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-modules',
            action='store_true',
            help='Skip module initialization',
        )
        parser.add_argument(
            '--skip-accounts',
            action='store_true',
            help='Skip accounting accounts initialization',
        )
        parser.add_argument(
            '--skip-categories',
            action='store_true',
            help='Skip expense/income categories initialization',
        )
        parser.add_argument(
            '--skip-branch',
            action='store_true',
            help='Skip default branch creation',
        )
        parser.add_argument(
            '--skip-tenant',
            action='store_true',
            help='Skip default tenant creation',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SETTING UP NEW ORGANIZATION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Get or create superuser for assignments
        try:
            superuser = User.objects.filter(is_superuser=True).first()
            if not superuser:
                self.stdout.write(self.style.WARNING(
                    'No superuser found. Please create one first with: python manage.py createsuperuser'
                ))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting superuser: {e}'))
            return
        
        # 1. Initialize Modules
        if not options['skip_modules']:
            self.stdout.write('\n1. Initializing modules...')
            try:
                from django.core.management import call_command
                call_command('init_modules')
                self.stdout.write(self.style.SUCCESS('  ✓ Modules initialized'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error initializing modules: {e}'))
        
        # 2. Initialize Accounting Accounts
        if not options['skip_accounts']:
            self.stdout.write('\n2. Initializing accounting accounts...')
            try:
                from django.core.management import call_command
                call_command('init_accounts')
                self.stdout.write(self.style.SUCCESS('  ✓ Accounting accounts initialized'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error initializing accounts: {e}'))
        
        # 3. Initialize Expense Categories
        if not options['skip_categories']:
            self.stdout.write('\n3. Initializing expense categories...')
            try:
                from django.core.management import call_command
                call_command('init_expense_categories')
                self.stdout.write(self.style.SUCCESS('  ✓ Expense categories initialized'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error initializing expense categories: {e}'))
        
        # 4. Create Default Tenant (Business/Company)
        from settings.models import Tenant
        tenant = None
        if not options.get('skip_tenant', False):
            self.stdout.write('\n4. Creating default tenant...')
            try:
                tenant, created = Tenant.objects.get_or_create(
                    code='DEFAULT',
                    defaults={
                        'name': 'CompleteByte Business',
                        'country': 'Kenya',
                        'city': 'Nairobi',
                        'owner': superuser,
                        'created_by': superuser,
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created default tenant: {tenant.name}'))
                else:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Default tenant already exists: {tenant.name}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error creating tenant: {e}'))
        
        # 5. Create Default Branch (Headquarters) - requires tenant
        if not options['skip_branch']:
            self.stdout.write('\n5. Creating default branch...')
            try:
                # Get tenant if not already created
                if not tenant:
                    tenant = Tenant.objects.filter(code='DEFAULT').first()
                
                if tenant and not Branch.objects.filter(is_headquarters=True, tenant=tenant).exists():
                    branch = Branch.objects.create(
                        tenant=tenant,
                        branch_code='HQ001',
                        name='Headquarters',
                        city='Nairobi',
                        country='Kenya',
                        is_active=True,
                        is_headquarters=True,
                        created_by=superuser
                    )
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created default branch: {branch.name}'))
                elif not tenant:
                    self.stdout.write(self.style.WARNING('  ⚠ Skipping branch creation: No tenant found'))
                else:
                    self.stdout.write(self.style.WARNING('  ⚠ Headquarters branch already exists'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error creating branch: {e}'))
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('SETUP COMPLETE!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('\nYour system is now ready to use!')
        self.stdout.write('\nYou can now:')
        self.stdout.write('  - Add products')
        self.stdout.write('  - Create sales')
        self.stdout.write('  - Manage inventory')
        self.stdout.write('  - Track expenses and income')
        self.stdout.write('  - View reports')
