"""Seed default product sizes and colors for variant picker."""

from django.core.management.base import BaseCommand

from products.models import Size, Color


DEFAULT_SIZES = [
    ('Small', 'S', 1),
    ('Medium', 'M', 2),
    ('Large', 'L', 3),
    ('Extra Large', 'XL', 4),
]

DEFAULT_COLORS = [
    ('Red', '#FF0000'),
    ('Blue', '#0000FF'),
    ('Green', '#008000'),
    ('Black', '#000000'),
    ('White', '#FFFFFF'),
    ('Brown', '#8B4513'),
    ('Grey', '#808080'),
]


class Command(BaseCommand):
    help = 'Create default sizes and colors (idempotent)'

    def handle(self, *args, **options):
        created_sizes = 0
        for name, code, order in DEFAULT_SIZES:
            _, created = Size.objects.get_or_create(
                code=code,
                defaults={'name': name, 'display_order': order, 'is_active': True},
            )
            if created:
                created_sizes += 1

        created_colors = 0
        for name, hex_code in DEFAULT_COLORS:
            _, created = Color.objects.get_or_create(
                name=name,
                defaults={'hex_code': hex_code, 'is_active': True},
            )
            if created:
                created_colors += 1

        self.stdout.write(self.style.SUCCESS(
            f'Sizes: {Size.objects.filter(is_active=True).count()} active '
            f'({created_sizes} new). '
            f'Colors: {Color.objects.filter(is_active=True).count()} active '
            f'({created_colors} new).'
        ))
