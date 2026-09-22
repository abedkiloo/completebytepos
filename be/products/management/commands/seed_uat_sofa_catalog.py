"""
Temporary UAT sofa-craft catalog (products + size/color variants only).

No sales, purchases, or stock movements — testers enter those.

  docker exec omuwenga-uat_backend python manage.py seed_uat_sofa_catalog
  docker exec omuwenga-uat_backend python manage.py seed_uat_sofa_catalog --revert
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import Category, Color, Product, ProductVariant, Size

SKU_PREFIX = 'UAT-SOFA-'
BARCODE_PREFIX = '8908'
PARENT_CATEGORY = 'UAT Sofa Craft'

SIZES = [
    ('2-Seater', 'UAT-2S', 1),
    ('3-Seater', 'UAT-3S', 2),
    ('4-Seater', 'UAT-4S', 3),
    ('54" fabric width', 'UAT-54', 4),
    ('60" fabric width', 'UAT-60', 5),
    ('One Size', 'UAT-OS', 6),
]

COLORS = [
    ('Cream', '#FFFDD0'),
    ('Charcoal', '#36454F'),
    ('Navy', '#000080'),
    ('Burgundy', '#800020'),
    ('Beige', '#F5F5DC'),
    ('Grey', '#808080'),
    ('Black', '#000000'),
    ('Walnut', '#5C4033'),
]

SOFA_SIZES = ('UAT-2S', 'UAT-3S', 'UAT-4S')
FABRIC_WIDTHS = ('UAT-54', 'UAT-60')
UPHOLSTERY_COLORS = ('Cream', 'Charcoal', 'Navy', 'Burgundy')
WOOD_COLORS = ('Walnut', 'Black', 'Beige')
METAL_COLORS = ('Black', 'Charcoal')

# Catalog only: stock stays 0 so testers record receiving/sales themselves.
CATALOG = [
    {
        'subcategory': 'UAT Fabric & Upholstery',
        'description': 'Upholstery fabrics for sofa sets',
        'products': [
            {
                'sku': 'VELVET',
                'name': 'Velvet upholstery fabric',
                'unit': 'roll',
                'cost': '650.00',
                'price': '980.00',
                'mrp': '1200.00',
                'sizes': FABRIC_WIDTHS,
                'colors': UPHOLSTERY_COLORS,
            },
            {
                'sku': 'CHENILLE',
                'name': 'Chenille upholstery fabric',
                'unit': 'roll',
                'cost': '520.00',
                'price': '790.00',
                'mrp': '950.00',
                'sizes': FABRIC_WIDTHS,
                'colors': UPHOLSTERY_COLORS,
            },
            {
                'sku': 'LINEN',
                'name': 'Linen blend sofa fabric',
                'unit': 'roll',
                'cost': '480.00',
                'price': '720.00',
                'mrp': '890.00',
                'sizes': FABRIC_WIDTHS,
                'colors': UPHOLSTERY_COLORS,
            },
            {
                'sku': 'FAUX-LEATHER',
                'name': 'Faux leather upholstery',
                'unit': 'roll',
                'cost': '890.00',
                'price': '1350.00',
                'mrp': '1600.00',
                'sizes': FABRIC_WIDTHS,
                'colors': ('Charcoal', 'Navy', 'Burgundy', 'Black'),
            },
        ],
    },
    {
        'subcategory': 'UAT Foam & Cushioning',
        'description': 'Foam and fill for seats and backs',
        'products': [
            {
                'sku': 'HD-FOAM',
                'name': 'High-density seat foam',
                'unit': 'piece',
                'cost': '2800.00',
                'price': '4200.00',
                'mrp': '4800.00',
                'sizes': SOFA_SIZES,
                'colors': (),
            },
            {
                'sku': 'BACK-FOAM',
                'name': 'Back cushion foam',
                'unit': 'piece',
                'cost': '1600.00',
                'price': '2450.00',
                'mrp': '2800.00',
                'sizes': SOFA_SIZES,
                'colors': (),
            },
            {
                'sku': 'DACRON',
                'name': 'Dacron batting wrap',
                'unit': 'roll',
                'cost': '350.00',
                'price': '520.00',
                'mrp': '600.00',
                'sizes': (),
                'colors': (),
            },
        ],
    },
    {
        'subcategory': 'UAT Cushion Covers',
        'description': 'Covers for sofa cushions and throws',
        'products': [
            {
                'sku': 'SEAT-COVER',
                'name': 'Sofa seat cushion cover',
                'unit': 'piece',
                'cost': '450.00',
                'price': '780.00',
                'mrp': '950.00',
                'sizes': SOFA_SIZES,
                'colors': UPHOLSTERY_COLORS,
            },
            {
                'sku': 'THROW-COVER',
                'name': 'Throw pillow cover',
                'unit': 'piece',
                'cost': '180.00',
                'price': '320.00',
                'mrp': '400.00',
                'sizes': ('UAT-OS',),
                'colors': UPHOLSTERY_COLORS,
            },
        ],
    },
    {
        'subcategory': 'UAT Wood & Frames',
        'description': 'Timber and sofa frame kits',
        'products': [
            {
                'sku': 'FRAME-KIT',
                'name': 'Hardwood sofa frame kit',
                'unit': 'piece',
                'cost': '12500.00',
                'price': '18500.00',
                'mrp': '21000.00',
                'sizes': SOFA_SIZES,
                'colors': WOOD_COLORS,
            },
            {
                'sku': 'PLYWOOD',
                'name': 'Plywood webbing board',
                'unit': 'piece',
                'cost': '950.00',
                'price': '1450.00',
                'mrp': '1700.00',
                'sizes': SOFA_SIZES,
                'colors': (),
            },
        ],
    },
    {
        'subcategory': 'UAT Springs & Hardware',
        'description': 'Springs, legs, and fasteners',
        'products': [
            {
                'sku': 'COIL-SPRING',
                'name': 'Coil spring pack',
                'unit': 'pack',
                'cost': '2200.00',
                'price': '3400.00',
                'mrp': '3900.00',
                'sizes': SOFA_SIZES,
                'colors': (),
            },
            {
                'sku': 'SOFA-LEG',
                'name': 'Wooden sofa leg set',
                'unit': 'pack',
                'cost': '680.00',
                'price': '1100.00',
                'mrp': '1350.00',
                'sizes': ('UAT-OS',),
                'colors': WOOD_COLORS,
            },
            {
                'sku': 'WEBBING',
                'name': 'Elastic jute webbing',
                'unit': 'roll',
                'cost': '420.00',
                'price': '650.00',
                'mrp': '750.00',
                'sizes': (),
                'colors': (),
            },
            {
                'sku': 'STAPLES',
                'name': 'Upholstery staples 8mm',
                'unit': 'box',
                'cost': '180.00',
                'price': '280.00',
                'mrp': '320.00',
                'sizes': (),
                'colors': (),
            },
        ],
    },
    {
        'subcategory': 'UAT Upholstery Supplies',
        'description': 'Thread, zippers, piping, adhesive',
        'products': [
            {
                'sku': 'THREAD',
                'name': 'Heavy-duty upholstery thread',
                'unit': 'piece',
                'cost': '90.00',
                'price': '160.00',
                'mrp': '200.00',
                'sizes': ('UAT-OS',),
                'colors': UPHOLSTERY_COLORS,
            },
            {
                'sku': 'ZIPPER',
                'name': 'Upholstery zipper',
                'unit': 'piece',
                'cost': '45.00',
                'price': '85.00',
                'mrp': '110.00',
                'sizes': SOFA_SIZES,
                'colors': METAL_COLORS,
            },
            {
                'sku': 'PIPING',
                'name': 'Piping / welt cord',
                'unit': 'roll',
                'cost': '120.00',
                'price': '210.00',
                'mrp': '250.00',
                'sizes': ('UAT-OS',),
                'colors': UPHOLSTERY_COLORS,
            },
            {
                'sku': 'WOOD-GLUE',
                'name': 'PVA wood glue 1L',
                'unit': 'bottle',
                'cost': '320.00',
                'price': '480.00',
                'mrp': '550.00',
                'sizes': (),
                'colors': (),
            },
        ],
    },
]


def product_sku(suffix):
    return f'{SKU_PREFIX}{suffix}'


def variant_sku(base, size=None, color=None):
    parts = [base]
    if size:
        parts.append(size.code.replace('UAT-', ''))
    if color:
        parts.append(color.name[:4].upper().replace(' ', ''))
    return '-'.join(parts)


def variant_barcode(index):
    return f'{BARCODE_PREFIX}{index:09d}'


class Command(BaseCommand):
    help = 'Seed (or --revert) UAT sofa-craft products with size/color variants. No transactional data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--revert',
            action='store_true',
            help='Delete only UAT-SOFA catalog products, UAT sizes, and UAT categories.',
        )

    def handle(self, *args, **options):
        if options['revert']:
            self._revert()
            return
        self._seed()

    @transaction.atomic
    def _seed(self):
        sizes = self._ensure_sizes()
        colors = self._ensure_colors()
        parent, _ = Category.objects.get_or_create(
            name=PARENT_CATEGORY,
            defaults={
                'description': 'Temporary UAT catalog for sofa-set craft materials',
                'is_active': True,
            },
        )

        created_products = 0
        created_variants = 0
        barcode_i = 1

        for group in CATALOG:
            sub, _ = Category.objects.get_or_create(
                name=group['subcategory'],
                defaults={
                    'parent': parent,
                    'description': group['description'],
                    'is_active': True,
                },
            )
            if sub.parent_id != parent.id:
                sub.parent = parent
                sub.save(update_fields=['parent'])

            for item in group['products']:
                sku = product_sku(item['sku'])
                barcode = variant_barcode(barcode_i)
                barcode_i += 1
                size_codes = item['sizes']
                color_names = item['colors']
                has_variants = bool(size_codes or color_names)

                product, created = Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        'name': item['name'],
                        'barcode': barcode,
                        'category': parent,
                        'subcategory': sub,
                        'mrp': Decimal(item['mrp']),
                        'price': Decimal(item['price']),
                        'cost': Decimal(item['cost']),
                        'stock_quantity': 0,
                        'low_stock_threshold': 5,
                        'unit': item['unit'],
                        'track_stock': True,
                        'is_active': True,
                        'has_variants': has_variants,
                        'description': (
                            f"{item['name']} for sofa-set making. "
                            'UAT seed — no opening stock; receive stock during testing.'
                        ),
                    },
                )
                if created:
                    created_products += 1

                selected_sizes = [sizes[c] for c in size_codes]
                selected_colors = [colors[n] for n in color_names]
                product.available_sizes.set(selected_sizes)
                product.available_colors.set(selected_colors)

                if not has_variants:
                    continue

                combos = self._variant_combos(selected_sizes, selected_colors)
                for size, color in combos:
                    v_sku = variant_sku(sku, size, color)
                    v_barcode = variant_barcode(barcode_i)
                    barcode_i += 1
                    _, v_created = ProductVariant.objects.update_or_create(
                        sku=v_sku,
                        defaults={
                            'product': product,
                            'size': size,
                            'color': color,
                            'barcode': v_barcode,
                            'stock_quantity': 0,
                            'low_stock_threshold': 5,
                            'is_active': True,
                            'price': None,
                            'cost': None,
                            'mrp': None,
                        },
                    )
                    if v_created:
                        created_variants += 1

        self.stdout.write(self.style.SUCCESS(
            f'UAT sofa catalog ready: {created_products} new products, '
            f'{created_variants} new variants. Stock is 0 (no transactions).'
        ))
        self.stdout.write('Revert later with: python manage.py seed_uat_sofa_catalog --revert')

    def _variant_combos(self, sizes, colors):
        if sizes and colors:
            return [(s, c) for s in sizes for c in colors]
        if sizes:
            return [(s, None) for s in sizes]
        return [(None, c) for c in colors]

    def _ensure_sizes(self):
        by_code = {}
        for name, code, order in SIZES:
            size, _ = Size.objects.get_or_create(
                code=code,
                defaults={'name': name, 'display_order': order, 'is_active': True},
            )
            by_code[code] = size
        return by_code

    def _ensure_colors(self):
        by_name = {}
        for name, hex_code in COLORS:
            color, _ = Color.objects.get_or_create(
                name=name,
                defaults={'hex_code': hex_code, 'is_active': True},
            )
            by_name[name] = color
        return by_name

    @transaction.atomic
    def _revert(self):
        products = Product.objects.filter(sku__startswith=SKU_PREFIX)
        product_count = products.count()
        variant_count = ProductVariant.objects.filter(product__in=products).count()
        products.delete()

        Size.objects.filter(code__startswith='UAT-').delete()
        sub_names = [g['subcategory'] for g in CATALOG]
        Category.objects.filter(name__in=sub_names).delete()
        Category.objects.filter(name=PARENT_CATEGORY).delete()

        self.stdout.write(self.style.SUCCESS(
            f'Reverted UAT sofa catalog: removed {product_count} products '
            f'and {variant_count} variants. Shared colors were left in place.'
        ))
