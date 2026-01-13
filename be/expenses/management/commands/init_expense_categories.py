from django.core.management.base import BaseCommand
from expenses.models import ExpenseCategory


class Command(BaseCommand):
    help = 'Initialize default expense categories'

    def handle(self, *args, **options):
        self.stdout.write('Initializing expense categories...')
        
        categories = [
            {'name': 'Office Supplies', 'description': 'Office supplies and stationery'},
            {'name': 'Rent & Utilities', 'description': 'Rent, electricity, water, internet, phone bills'},
            {'name': 'Transportation', 'description': 'Fuel, vehicle maintenance, parking, taxi fares'},
            {'name': 'Marketing & Advertising', 'description': 'Marketing campaigns, advertisements, promotions'},
            {'name': 'Professional Services', 'description': 'Legal, accounting, consulting services'},
            {'name': 'Maintenance & Repairs', 'description': 'Equipment maintenance, repairs, servicing'},
            {'name': 'Travel & Accommodation', 'description': 'Business travel, hotel, meals'},
            {'name': 'Training & Development', 'description': 'Employee training, courses, workshops'},
            {'name': 'Insurance', 'description': 'Business insurance, health insurance'},
            {'name': 'Taxes & Fees', 'description': 'Business licenses, permits, taxes'},
            {'name': 'Equipment & Tools', 'description': 'Purchase of equipment, tools, machinery'},
            {'name': 'Raw Materials', 'description': 'Raw materials for production'},
            {'name': 'Packaging', 'description': 'Packaging materials and supplies'},
            {'name': 'Shipping & Delivery', 'description': 'Shipping costs, delivery charges'},
            {'name': 'Bank Charges', 'description': 'Bank fees, transaction charges'},
            {'name': 'Miscellaneous', 'description': 'Other expenses not categorized'},
        ]
        
        created_count = 0
        for cat_data in categories:
            category, created = ExpenseCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created category: {category.name}'))
            else:
                self.stdout.write(f'Category already exists: {category.name}')
        
        self.stdout.write(self.style.SUCCESS(f'\nExpense categories initialized! Created {created_count} new categories.'))

