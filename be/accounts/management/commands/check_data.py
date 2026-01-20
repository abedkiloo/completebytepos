"""
Management command to check if the database has data.
Usage: python manage.py check_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Count
from django.apps import apps


class Command(BaseCommand):
    help = 'Check if the database has data across all key models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed counts for each model',
        )
        parser.add_argument(
            '--min-count',
            type=int,
            default=0,
            help='Minimum count threshold to consider as "has data" (default: 0)',
        )

    def handle(self, *args, **options):
        detailed = options['detailed']
        min_count = options['min_count']
        
        self.stdout.write(self.style.SUCCESS('\n=== Database Data Check ===\n'))
        
        # Key models to check
        models_to_check = {
            'User': User,
            'Product': None,
            'ProductVariant': None,
            'Category': None,
            'Customer': None,
            'Sale': None,
            'SaleItem': None,
            'Invoice': None,
            'Payment': None,
            'Expense': None,
            'ExpenseCategory': None,
            'Income': None,
            'IncomeCategory': None,
            'Supplier': None,
            'Employee': None,
            'StockMovement': None,
            'BankAccount': None,
            'BankTransaction': None,
            'MoneyTransfer': None,
            'Account': None,
            'AccountType': None,
            'JournalEntry': None,
            'Transaction': None,
        }
        
        # Try to import models dynamically
        model_instances = {}
        for model_name, model_class in models_to_check.items():
            if model_class is None:
                # Try to find the model in installed apps
                for app_config in apps.get_app_configs():
                    try:
                        model_class = apps.get_model(app_config.label, model_name)
                        if model_class:
                            model_instances[model_name] = model_class
                            break
                    except LookupError:
                        continue
            else:
                model_instances[model_name] = model_class
        
        # Check each model
        total_models = 0
        models_with_data = 0
        results = []
        
        for model_name, model_class in model_instances.items():
            if model_class is None:
                continue
                
            total_models += 1
            try:
                count = model_class.objects.count()
                has_data = count > min_count
                
                if has_data:
                    models_with_data += 1
                
                status = '✓' if has_data else '✗'
                status_style = self.style.SUCCESS if has_data else self.style.WARNING
                
                results.append({
                    'name': model_name,
                    'count': count,
                    'has_data': has_data,
                    'status': status,
                    'style': status_style
                })
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ {model_name}: Error - {str(e)}')
                )
        
        # Display results
        if detailed:
            self.stdout.write('\nDetailed Results:\n')
            for result in sorted(results, key=lambda x: x['name']):
                status_text = f"{result['status']} {result['name']}"
                count_text = f"Count: {result['count']}"
                self.stdout.write(
                    f"{result['style'](status_text):<30} {count_text}"
                )
        else:
            # Summary view
            self.stdout.write('\nSummary:\n')
            for result in sorted(results, key=lambda x: x['name']):
                status_text = f"{result['status']} {result['name']}"
                if result['has_data']:
                    self.stdout.write(
                        f"{result['style'](status_text):<30} ({result['count']} records)"
                    )
                else:
                    self.stdout.write(result['style'](status_text))
        
        # Overall summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'\nTotal Models Checked: {total_models}')
        self.stdout.write(
            self.style.SUCCESS(f'Models with Data: {models_with_data}')
        )
        self.stdout.write(
            self.style.WARNING(f'Models without Data: {total_models - models_with_data}')
        )
        
        if models_with_data == 0:
            self.stdout.write(
                self.style.ERROR('\n⚠️  WARNING: Database appears to be empty!')
            )
            self.stdout.write('   Consider running: python manage.py populate_test_data')
        elif models_with_data < total_models * 0.3:
            self.stdout.write(
                self.style.WARNING('\n⚠️  NOTE: Database has limited data.')
            )
            self.stdout.write('   Consider running: python manage.py populate_test_data')
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✓ Database has sufficient data.')
            )
        
        self.stdout.write('\n' + '='*50 + '\n')
