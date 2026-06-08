"""
Optional demo catalog: one category and three sample products.

Not run automatically — use only for local demos:
  python manage.py seed_demo_catalog
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from products.models import Category, Product

DEMO_PRODUCTS = [
    {
        'name': 'Bottled Water 500ml',
        'sku': 'DEMO-WATER-500',
        'barcode': '8901000000001',
        'mrp': '50.00',
        'price': '40.00',
        'cost': '25.00',
        'stock': 100,
        'unit': 'bottle',
    },
    {
        'name': 'Bread Loaf White',
        'sku': 'DEMO-BREAD-WHT',
        'barcode': '8901000000002',
        'mrp': '80.00',
        'price': '70.00',
        'cost': '45.00',
        'stock': 50,
        'unit': 'piece',
    },
    {
        'name': 'Cooking Oil 1L',
        'sku': 'DEMO-OIL-1L',
        'barcode': '8901000000003',
        'mrp': '350.00',
        'price': '320.00',
        'cost': '260.00',
        'stock': 30,
        'unit': 'bottle',
    },
]


class Command(BaseCommand):
    help = 'Optional: seed 1 category and 3 demo products (not run on install)'

    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(
            name='General',
            defaults={'description': 'Default demo category', 'is_active': True},
        )

        created_count = 0
        for item in DEMO_PRODUCTS:
            product, created = Product.objects.update_or_create(
                sku=item['sku'],
                defaults={
                    'name': item['name'],
                    'barcode': item['barcode'],
                    'category': category,
                    'mrp': Decimal(item['mrp']),
                    'price': Decimal(item['price']),
                    'cost': Decimal(item['cost']),
                    'stock_quantity': item['stock'],
                    'low_stock_threshold': 5,
                    'unit': item['unit'],
                    'track_stock': True,
                    'is_active': True,
                    'has_variants': False,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Product: {product.name}'))
            else:
                self.stdout.write(f'  · Product exists: {product.name}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Demo catalog ready ({created_count} new, {len(DEMO_PRODUCTS)} total SKUs)'
        ))
