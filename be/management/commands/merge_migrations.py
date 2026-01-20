"""
Management command to merge all migrations in each module into a single 0001_initial.py migration.
This creates a clean slate for fresh installations.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
import os
import shutil
from pathlib import Path
import django
from django.conf import settings

class Command(BaseCommand):
    help = 'Merge all migrations in each module into single 0001_initial.py files'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('MERGING MIGRATIONS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        base_dir = Path(settings.BASE_DIR)
        apps = [
            'accounts', 'settings', 'accounting', 'products', 'sales', 
            'inventory', 'expenses', 'income', 'bankaccounts', 'transfers',
            'barcodes', 'reports', 'suppliers'
        ]
        
        for app in apps:
            migrations_dir = base_dir / app / 'migrations'
            if not migrations_dir.exists():
                self.stdout.write(self.style.WARNING(f'  ⚠ {app}: migrations directory not found'))
                continue
            
            # Get all migration files except __init__.py
            migration_files = sorted([f for f in migrations_dir.glob('*.py') if f.name != '__init__.py'])
            
            if not migration_files:
                self.stdout.write(self.style.WARNING(f'  ⚠ {app}: No migration files found'))
                continue
            
            # Keep only 0001_initial.py if it exists, otherwise use the first one
            initial_migration = migrations_dir / '0001_initial.py'
            
            if len(migration_files) > 1 or (len(migration_files) == 1 and migration_files[0].name != '0001_initial.py'):
                # Delete all migration files except __init__.py
                for f in migration_files:
                    if f.name != '0001_initial.py':
                        f.unlink()
                        self.stdout.write(self.style.SUCCESS(f'  ✓ {app}: Deleted {f.name}'))
                
                # If 0001_initial.py doesn't exist, rename the first one
                if not initial_migration.exists() and migration_files:
                    first_migration = migration_files[0]
                    if first_migration.exists():
                        first_migration.rename(initial_migration)
                        self.stdout.write(self.style.SUCCESS(f'  ✓ {app}: Renamed {first_migration.name} to 0001_initial.py'))
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ {app}: Migration consolidated'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('Migration merge complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('\nNext steps:')
        self.stdout.write('1. Delete db.sqlite3 (if exists)')
        self.stdout.write('2. Run: python manage.py migrate')
        self.stdout.write('3. Run: python manage.py fresh_install --test-data')
