"""
Complete fresh installation command - runs all setup steps in order
This is the command that powers the one-click installation UI
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import transaction
from settings.models import Tenant
import os
import sys

User = get_user_model()


class Command(BaseCommand):
    help = 'Complete fresh installation - deletes database, runs migrations, and sets up everything'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-db-delete',
            action='store_true',
            help='Skip database deletion (use if database is already fresh)',
        )
        parser.add_argument(
            '--skip-test-data',
            action='store_true',
            help='Skip test data population',
        )
        parser.add_argument(
            '--test-data',
            action='store_true',
            help='Populate comprehensive soft furnishings data (users, products, customers, sales, expenses)',
        )
        parser.add_argument(
            '--users',
            type=int,
            default=20,
            help='Number of users to create (default: 20)',
        )
        parser.add_argument(
            '--products',
            type=int,
            default=200,
            help='Number of products to create (default: 200)',
        )
        parser.add_argument(
            '--customers',
            type=int,
            default=50,
            help='Number of customers to create (default: 50)',
        )
        parser.add_argument(
            '--num-sales',
            type=int,
            default=100,
            dest='num_sales',
            help='Number of sales to create (default: 100)',
        )
        parser.add_argument(
            '--num-expenses',
            type=int,
            default=30,
            dest='num_expenses',
            help='Number of expenses to create (default: 30)',
        )
        parser.add_argument(
            '--sales',
            type=int,
            default=100,
            help='Number of sales to create (default: 100)',
        )
        parser.add_argument(
            '--expenses',
            type=int,
            default=30,
            help='Number of expenses to create (default: 30)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('COMPLETE FRESH INSTALLATION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        try:
            with transaction.atomic():
                # Step 1: Delete database if needed
                if not options['skip_db_delete']:
                    self.stdout.write('Step 1: Preparing fresh database...')
                    db_path = 'db.sqlite3'
                    if os.path.exists(db_path):
                        os.remove(db_path)
                        self.stdout.write(self.style.SUCCESS('  ✓ Existing database deleted'))
                    else:
                        self.stdout.write(self.style.SUCCESS('  ✓ No existing database found'))
                else:
                    self.stdout.write('Step 1: Skipping database deletion...')

                # Step 2: Create migrations (skip if migrations already exist)
                self.stdout.write('\nStep 2: Creating migrations...')
                try:
                    call_command('makemigrations', verbosity=0)
                    self.stdout.write(self.style.SUCCESS('  ✓ Migrations created'))
                except Exception as e:
                    error_msg = str(e)
                    if 'Conflicting migrations' in error_msg or 'No changes detected' in error_msg:
                        self.stdout.write(self.style.SUCCESS('  ✓ Migrations already exist'))
                    else:
                        self.stdout.write(self.style.WARNING(f'  ⚠ Migration creation: {error_msg[:100]}'))

                # Step 3: Run migrations
                self.stdout.write('\nStep 3: Running migrations...')
                try:
                    # Try normal migrate first
                    call_command('migrate', verbosity=0, interactive=False)
                    self.stdout.write(self.style.SUCCESS('  ✓ Migrations applied'))
                except Exception as e:
                    # If that fails, try with --fake-initial
                    try:
                        call_command('migrate', '--fake-initial', verbosity=0, interactive=False)
                        self.stdout.write(self.style.SUCCESS('  ✓ Migrations applied (with --fake-initial)'))
                    except Exception as e2:
                        self.stdout.write(self.style.ERROR(f'  ✗ Migration failed: {str(e2)[:100]}'))
                        raise

                # Step 4: Create superuser
                self.stdout.write('\nStep 4: Creating superuser...')
                try:
                    user, created = User.objects.get_or_create(
                        username='admin@3@1',
                        defaults={
                            'email': 'admin@3@1',
                            'is_staff': True,
                            'is_superuser': True,
                            'is_active': True
                        }
                    )
                    user.set_password('admin@3@1')
                    user.save()
                    if created:
                        self.stdout.write(self.style.SUCCESS('  ✓ Superuser created (username: admin@3@1, password: admin@3@1)'))
                    else:
                        self.stdout.write(self.style.SUCCESS('  ✓ Superuser updated (username: admin@3@1, password: admin@3@1)'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Superuser creation failed: {str(e)[:100]}'))
                    raise

                # Step 5: Initialize permissions and roles
                self.stdout.write('\nStep 5: Initializing permissions and roles...')
                try:
                    call_command('init_permissions', verbosity=0)
                    self.stdout.write(self.style.SUCCESS('  ✓ Permissions and roles initialized'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Permissions initialization: {str(e)[:100]}'))

                # Step 6: Initialize modules
                self.stdout.write('\nStep 6: Initializing modules and features...')
                try:
                    call_command('init_modules', verbosity=0)
                    self.stdout.write(self.style.SUCCESS('  ✓ Modules and features initialized'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Module initialization: {str(e)[:100]}'))

                # Step 7: Initialize accounting accounts
                self.stdout.write('\nStep 7: Initializing accounting accounts...')
                try:
                    call_command('init_accounts', verbosity=0)
                    self.stdout.write(self.style.SUCCESS('  ✓ Accounting accounts initialized'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Accounts initialization: {str(e)[:100]}'))

                # Step 8: Initialize expense categories
                self.stdout.write('\nStep 8: Initializing expense categories...')
                try:
                    call_command('init_expense_categories', verbosity=0)
                    self.stdout.write(self.style.SUCCESS('  ✓ Expense categories initialized'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Expense categories initialization: {str(e)[:100]}'))

                # Step 9: Setup new organization (tenant and branch)
                self.stdout.write('\nStep 9: Setting up organization...')
                try:
                    call_command('setup_new_organization', verbosity=0)
                    self.stdout.write(self.style.SUCCESS('  ✓ Organization setup complete'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Organization setup: {str(e)[:100]}'))

                # Step 10: Populate data (optional)
                if options['test_data'] and not options['skip_test_data']:
                    self.stdout.write('\nStep 10: Populating comprehensive soft furnishings data...')
                    try:
                        # Get sales and expenses values - support both --sales/--expenses and --num-sales/--num-expenses
                        sales_count = options.get('sales') or options.get('num_sales', 100)
                        expenses_count = options.get('expenses') or options.get('num_expenses', 30)
                        
                        call_command('populate_test_data',
                                    users=options['users'],
                                    products=options['products'],
                                    customers=options['customers'],
                                    sales=sales_count,
                                    expenses=expenses_count,
                                    verbosity=1)
                        self.stdout.write(self.style.SUCCESS(
                            f'  ✓ Soft furnishings data populated '
                            f'({options["users"]} users, {options["products"]} products, '
                            f'{options["customers"]} customers, {sales_count} sales, '
                            f'{expenses_count} expenses)'
                        ))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'  ⚠ Data population: {str(e)[:100]}'))
                else:
                    self.stdout.write('\nStep 10: Skipping data population...')
                    self.stdout.write(self.style.WARNING('  💡 Tip: Use --test-data to populate comprehensive soft furnishings data'))

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('INSTALLATION COMPLETE!'))
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write('')
            self.stdout.write('Login credentials:')
            self.stdout.write('  Username: admin@3@1')
            self.stdout.write('  Password: admin@3@1')
            self.stdout.write('')
            self.stdout.write('⚠️  IMPORTANT: Change the default password after first login!')
            self.stdout.write('')

        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('=' * 70))
            self.stdout.write(self.style.ERROR('INSTALLATION FAILED!'))
            self.stdout.write(self.style.ERROR('=' * 70))
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            self.stdout.write('')
            raise
