from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from products.models import Category, Product, Size, Color, ProductVariant
from decimal import Decimal
import random
import uuid
from io import BytesIO
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class Command(BaseCommand):
    help = 'Generate products for sofa set making with sizes and colors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-images',
            action='store_true',
            help='Generate products with images (uses placeholder images)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Generating sofa set materials with variants...')
        
        # Create default sizes
        self.stdout.write('Creating default sizes...')
        default_sizes = [
            {'name': 'Small (2-Seater)', 'code': 'S', 'order': 1},
            {'name': 'Medium (3-Seater)', 'code': 'M', 'order': 2},
            {'name': 'Large (4-Seater)', 'code': 'L', 'order': 3},
            {'name': 'Extra Large (5-Seater)', 'code': 'XL', 'order': 4},
            {'name': 'Sectional', 'code': 'SEC', 'order': 5},
            {'name': 'Corner Unit', 'code': 'COR', 'order': 6},
            {'name': 'Ottoman', 'code': 'OTT', 'order': 7},
            {'name': 'One Size', 'code': 'OS', 'order': 8},
        ]
        sizes = {}
        for size_data in default_sizes:
            size, created = Size.objects.get_or_create(
                code=size_data['code'],
                defaults={
                    'name': size_data['name'],
                    'display_order': size_data['order'],
                    'is_active': True
                }
            )
            sizes[size_data['code']] = size
            if created:
                self.stdout.write(f'  Created size: {size.name}')
        
        # Create default colors
        self.stdout.write('Creating default colors...')
        default_colors = [
            {'name': 'Red', 'hex': '#FF0000'},
            {'name': 'Blue', 'hex': '#0000FF'},
            {'name': 'Green', 'hex': '#00FF00'},
            {'name': 'Yellow', 'hex': '#FFFF00'},
            {'name': 'Black', 'hex': '#000000'},
            {'name': 'White', 'hex': '#FFFFFF'},
            {'name': 'Gray', 'hex': '#808080'},
            {'name': 'Brown', 'hex': '#A52A2A'},
            {'name': 'Beige', 'hex': '#F5F5DC'},
            {'name': 'Navy', 'hex': '#000080'},
            {'name': 'Maroon', 'hex': '#800000'},
            {'name': 'Cream', 'hex': '#FFFDD0'},
            {'name': 'Charcoal', 'hex': '#36454F'},
            {'name': 'Burgundy', 'hex': '#800020'},
            {'name': 'Tan', 'hex': '#D2B48C'},
        ]
        colors = {}
        for color_data in default_colors:
            color, created = Color.objects.get_or_create(
                name=color_data['name'],
                defaults={
                    'hex_code': color_data['hex'],
                    'is_active': True
                }
            )
            colors[color_data['name']] = color
            if created:
                self.stdout.write(f'  Created color: {color.name}')
        
        # Create main category
        main_category, created = Category.objects.get_or_create(
            name='Sofa Set Materials',
            defaults={
                'description': 'Materials and components for making sofa sets',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created main category: {main_category.name}'))
        
        # Define sofa set material categories
        sub_categories_data = [
            {
                'name': 'Fabric & Upholstery',
                'description': 'Fabrics and materials for sofa upholstery',
                'products': [
                    'Cotton Fabric', 'Linen Fabric', 'Polyester Fabric', 'Velvet Fabric', 'Leather Sheet',
                    'Suede Fabric', 'Microfiber Fabric', 'Chenille Fabric', 'Tweed Fabric', 'Canvas Fabric',
                    'Denim Fabric', 'Jacquard Fabric', 'Brocade Fabric', 'Damask Fabric', 'Satin Fabric',
                    'Silk Fabric', 'Wool Fabric', 'Acrylic Fabric', 'Nylon Fabric', 'Rayon Fabric',
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,  # Changed to True - fabrics can have sizes
            },
            {
                'name': 'Foam & Cushioning',
                'description': 'Foam and cushioning materials for sofas',
                'products': [
                    'High Density Foam', 'Medium Density Foam', 'Low Density Foam', 'Memory Foam', 'Gel Foam',
                    'Rebonded Foam', 'HR Foam', 'PU Foam', 'EVA Foam', 'Neoprene Foam',
                    'Cushion Foam', 'Seat Cushion Foam', 'Back Cushion Foam', 'Armrest Foam', 'Headrest Foam',
                    'Polyester Fiber', 'Polyester Fill', 'Polyester Batting', 'Polyester Stuffing', 'Polyester Padding',
                    'Cotton Batting', 'Cotton Fill', 'Cotton Stuffing', 'Cotton Padding', 'Cotton Wadding',
                    'Down Feather', 'Feather Fill', 'Feather Stuffing', 'Synthetic Down', 'Down Alternative',
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,
            },
            {
                'name': 'Cushion Covers',
                'description': 'Covers for sofa cushions and pillows',
                'products': [
                    'Cushion Cover', 'Pillow Cover', 'Throw Pillow Cover', 'Accent Pillow Cover', 'Bolster Cover',
                    'Lumbar Pillow Cover', 'Square Pillow Cover', 'Rectangular Pillow Cover', 'Round Pillow Cover',
                    'Sofa Seat Cover', 'Sofa Back Cover', 'Armrest Cover', 'Headrest Cover', 'Ottoman Cover',
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,
            },
            {
                'name': 'Wood & Frame Materials',
                'description': 'Wood and materials for sofa frames',
                'products': [
                    'Hardwood Plank', 'Softwood Beam', 'Plywood Sheet', 'MDF Board', 'Particle Board',
                    'Oak Timber', 'Pine Timber', 'Cedar Wood', 'Mahogany Plank', 'Teak Wood',
                    'Sofa Frame Kit', 'Chair Frame Kit', 'Ottoman Frame Kit', 'Frame Corner Block', 'Frame Joint Block',
                    'Frame Support Block', 'Frame Reinforcement Block', 'Frame Bracket', 'Frame Corner Brace', 'Frame T Brace',
                ],
                'has_variants': True,  # Changed to True - wood can have sizes
                'use_colors': False,
                'use_sizes': True,
            },
            {
                'name': 'Metal Hardware',
                'description': 'Metal components for sofa construction',
                'products': [
                    'Steel Frame', 'Aluminum Frame', 'Metal Leg', 'Metal Bracket', 'Steel Rod',
                    'Metal Spring', 'Coil Spring', 'Sinuous Spring', 'Zigzag Spring', 'No Sag Spring',
                    'Drawer Slide', 'Ball Bearing Slide', 'Soft Close Slide', 'Caster', 'Swivel Caster',
                    'Metal Screw', 'Wood Screw', 'Machine Screw', 'Bolt', 'Hex Bolt',
                ],
                'has_variants': True,  # Changed to True - hardware can have sizes
                'use_colors': False,
                'use_sizes': True,
            },
            {
                'name': 'Upholstery Supplies',
                'description': 'Threads, needles, and upholstery supplies',
                'products': [
                    'Upholstery Thread', 'Heavy Duty Thread', 'Nylon Thread', 'Polyester Thread', 'Cotton Thread',
                    'Upholstery Needle', 'Curved Needle', 'Straight Needle', 'Tuffing Needle', 'Button Needle',
                    'Zipper', 'Upholstery Zipper', 'Invisible Zipper', 'Heavy Duty Zipper', 'Decorative Zipper',
                    'Upholstery Button', 'Covered Button', 'Snap Button', 'Toggle Button', 'Decorative Button',
                    'Upholstery Tack', 'Decorative Tack', 'Gimp Trim', 'Cord Trim', 'Fringe Trim',
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,  # Changed to True - supplies can have sizes
            },
            {
                'name': 'Decorative Elements',
                'description': 'Decorative trims and accessories',
                'products': [
                    'Decorative Trim', 'Gimp Trim', 'Cord Trim', 'Fringe Trim', 'Tassel Trim',
                    'Braid Trim', 'Ribbon Trim', 'Lace Trim', 'Piping Trim', 'Welt Trim',
                    'Welt Cord', 'Piping Cord', 'Bias Tape', 'Double Fold Bias', 'Single Fold Bias',
                    'Decorative Button', 'Covered Button', 'Tuffing Button', 'Diamond Tuffing', 'Channel Tuffing',
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,  # Changed to True - decorative elements can have sizes
            },
            {
                'name': 'Adhesives & Fasteners',
                'description': 'Glues, adhesives and fastening materials',
                'products': [
                    'Wood Glue', 'Carpenter Glue', 'PVA Glue', 'Epoxy Glue', 'Super Glue',
                    'Contact Cement', 'Construction Adhesive', 'Spray Adhesive', 'Fabric Glue', 'Foam Adhesive',
                    'Staple Gun', 'Electric Staple Gun', 'Upholstery Staple Gun', 'Crown Stapler', 'Staple',
                ],
                'has_variants': True,  # Changed to True - adhesives can have sizes
                'use_colors': False,
                'use_sizes': True,
            },
        ]
        
        # Create sub-categories and products
        total_products = 0
        products_per_category = 50  # 8 categories * 50 = 400 products
        
        for cat_data in sub_categories_data:
            # Create sub-category
            sub_category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'parent': main_category,
                    'description': cat_data['description'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created category: {sub_category.name}'))
            
            # Get product templates for this category
            product_templates = cat_data['products']
            has_variants = cat_data.get('has_variants', False)
            use_colors = cat_data.get('use_colors', False)
            use_sizes = cat_data.get('use_sizes', False)
            
            # Generate products for this category
            category_products = 0
            for i in range(products_per_category):
                # Cycle through product templates
                template_index = i % len(product_templates)
                base_name = product_templates[template_index]
                
                # Create variations for products beyond template list
                if i >= len(product_templates):
                    variations = ['Standard', 'Premium', 'Deluxe', 'Economy', 'Heavy Duty']
                    variation = variations[i % len(variations)]
                    product_name = f"{base_name} - {variation}"
                else:
                    product_name = base_name
                
                # Generate product data
                cost = Decimal(str(round(random.uniform(100, 5000), 2)))
                price = cost * Decimal(str(round(random.uniform(1.3, 2.5), 2)))  # 30% to 150% markup
                stock = random.randint(0, 300)
                low_stock_threshold = random.randint(10, 50)
                
                # Generate unique SKU
                category_prefix = sub_category.name[:3].upper().replace(' ', '')
                sku = f"SOFA-{category_prefix}-{str(i+1).zfill(4)}"
                
                # Generate unique barcode
                barcode = f"BC{random.randint(100000000000, 999999999999)}"
                while Product.objects.filter(barcode=barcode).exists():
                    barcode = f"BC{random.randint(100000000000, 999999999999)}"
                
                # Create product
                product = Product.objects.create(
                    name=product_name,
                    sku=sku,
                    barcode=barcode,
                    category=main_category,
                    subcategory=sub_category,
                    price=price,
                    cost=cost,
                    stock_quantity=stock,
                    low_stock_threshold=low_stock_threshold,
                    description=f"{product_name} for {sub_category.name.lower()} in sofa set making. High quality material suitable for professional use.",
                    unit='piece',
                    is_taxable=random.choice([True, False]),
                    track_stock=True,
                    is_active=True,
                    has_variants=has_variants,
                )
                
                # Add sizes and colors if product has variants
                if has_variants:
                    if use_sizes:
                        # Add 3-6 random sizes
                        selected_sizes = random.sample(list(sizes.values()), k=min(random.randint(3, 6), len(sizes)))
                        product.available_sizes.set(selected_sizes)
                    
                    if use_colors:
                        # Add 4-10 random colors
                        selected_colors = random.sample(list(colors.values()), k=min(random.randint(4, 10), len(colors)))
                        product.available_colors.set(selected_colors)
                    
                    # Create variants
                    variant_count = 0
                    if use_sizes and use_colors and product.available_sizes.exists() and product.available_colors.exists():
                        # Create variants for each size/color combination
                        for size in product.available_sizes.all():
                            for color in product.available_colors.all():
                                variant_price = price * Decimal(str(round(random.uniform(0.95, 1.15), 2)))
                                variant_cost = cost * Decimal(str(round(random.uniform(0.95, 1.10), 2)))
                                variant_stock = random.randint(0, 150)
                                
                                ProductVariant.objects.create(
                                    product=product,
                                    size=size,
                                    color=color,
                                    price=variant_price,
                                    cost=variant_cost,
                                    stock_quantity=variant_stock,
                                    low_stock_threshold=low_stock_threshold,
                                    is_active=True
                                )
                                variant_count += 1
                    
                    elif use_colors and product.available_colors.exists():
                        # Create variants for each color
                        for color in product.available_colors.all():
                            variant_price = price * Decimal(str(round(random.uniform(0.95, 1.15), 2)))
                            variant_cost = cost * Decimal(str(round(random.uniform(0.95, 1.10), 2)))
                            variant_stock = random.randint(0, 150)
                            
                            ProductVariant.objects.create(
                                product=product,
                                size=None,
                                color=color,
                                price=variant_price,
                                cost=variant_cost,
                                stock_quantity=variant_stock,
                                low_stock_threshold=low_stock_threshold,
                                is_active=True
                            )
                            variant_count += 1
                    
                    elif use_sizes and product.available_sizes.exists():
                        # Create variants for each size
                        for size in product.available_sizes.all():
                            variant_price = price * Decimal(str(round(random.uniform(0.95, 1.15), 2)))
                            variant_cost = cost * Decimal(str(round(random.uniform(0.95, 1.10), 2)))
                            variant_stock = random.randint(0, 150)
                            
                            ProductVariant.objects.create(
                                product=product,
                                size=size,
                                color=None,
                                price=variant_price,
                                cost=variant_cost,
                                stock_quantity=variant_stock,
                                low_stock_threshold=low_stock_threshold,
                                is_active=True
                            )
                            variant_count += 1
                    
                    if variant_count > 0 and (i + 1) % 10 == 0:
                        self.stdout.write(f'    Created {variant_count} variants for {product_name}')
                
                # Generate and save image if requested
                if options['with_images'] and PIL_AVAILABLE:
                    try:
                        image = self.generate_product_image(product_name, sub_category.name)
                        if image:
                            product.image.save(
                                f"{product.sku}.png",
                                ContentFile(image),
                                save=True
                            )
                    except Exception as e:
                        pass
                
                category_products += 1
                total_products += 1
                
                if (i + 1) % 20 == 0:
                    self.stdout.write(f'  Created {i + 1}/{products_per_category} products in {sub_category.name}...')
            
            self.stdout.write(self.style.SUCCESS(
                f'✓ Created {category_products} products in {sub_category.name}'
            ))
        
        # Create superuser if doesn't exist
        from django.contrib.auth.models import User
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
            self.stdout.write(self.style.SUCCESS('Created default superuser: admin/admin123'))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Successfully generated {total_products} products across {len(sub_categories_data)} categories!'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'✅ Created {Size.objects.count()} sizes and {Color.objects.count()} colors'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'✅ Created {ProductVariant.objects.count()} product variants'
        ))

    def generate_product_image(self, product_name, category_name):
        """Generate a simple product image with text"""
        if not PIL_AVAILABLE:
            return None
            
        try:
            width, height = 400, 400
            image = Image.new('RGB', (width, height), color=(240, 240, 240))
            draw = ImageDraw.Draw(image)
            
            try:
                font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
                font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
            except:
                try:
                    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
                    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
                except:
                    font_large = ImageFont.load_default()
                    font_small = ImageFont.load_default()
            
            draw.text((width // 2, 50), category_name, fill=(100, 100, 100), font=font_small, anchor="mm")
            
            words = product_name.split()
            lines = []
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font_large)
                if bbox[2] - bbox[0] < width - 40:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(' '.join(current_line))
            
            y_start = height // 2 - (len(lines) * 30) // 2
            for i, line in enumerate(lines):
                draw.text((width // 2, y_start + i * 30), line, fill=(50, 50, 50), font=font_large, anchor="mm")
            
            img_io = BytesIO()
            image.save(img_io, format='PNG')
            img_io.seek(0)
            return img_io.getvalue()
        except Exception as e:
            return None
