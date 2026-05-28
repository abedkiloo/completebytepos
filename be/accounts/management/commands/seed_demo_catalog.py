"""
Seed a minimal catalog: one category and three demo products with stock.

Idempotent — safe to run on every Docker start.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.role_definitions import DEMO_PRODUCTS
from products.models import Category, Product


class Command(BaseCommand):
    help = 'Seed 1 category and 3 demo products (no bulk test data)'

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
