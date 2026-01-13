"""
Management command to populate database with test data:
- 100 users
- 100 customers
- 1000 products with categories and variants
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile, Role
from sales.models import Customer
from products.models import Category, Product, Size, Color, ProductVariant
from settings.models import Branch
from decimal import Decimal
import random
import uuid
from datetime import datetime, timedelta

# Try to use Faker if available, otherwise use manual data
try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False


class Command(BaseCommand):
    help = 'Populate database with test data: 100 users, 100 customers, 1000 products with variants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=100,
            help='Number of users to create (default: 100)',
        )
        parser.add_argument(
            '--customers',
            type=int,
            default=100,
            help='Number of customers to create (default: 100)',
        )
        parser.add_argument(
            '--products',
            type=int,
            default=1000,
            help='Number of products to create (default: 1000)',
        )
        parser.add_argument(
            '--skip-users',
            action='store_true',
            help='Skip user creation',
        )
        parser.add_argument(
            '--skip-customers',
            action='store_true',
            help='Skip customer creation',
        )
        parser.add_argument(
            '--skip-products',
            action='store_true',
            help='Skip product creation',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('POPULATING TEST DATA'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Initialize Faker if available
        if FAKER_AVAILABLE:
            fake = Faker()
            self.fake = fake
        else:
            self.fake = None
            self.stdout.write(self.style.WARNING(
                'Faker library not available. Install with: pip install faker'
            ))
        
        # Get or create superuser for assignments
        superuser = User.objects.filter(is_superuser=True).first()
        if not superuser:
            superuser = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
            self.stdout.write(self.style.SUCCESS('Created admin superuser'))
        
        # Get or create default branch
        branch = Branch.objects.filter(is_headquarters=True).first()
        if not branch:
            branch = Branch.objects.create(
                branch_code='HQ001',
                name='Headquarters',
                city='Nairobi',
                country='Kenya',
                is_active=True,
                is_headquarters=True,
                created_by=superuser
            )
        
        # Get roles
        admin_role = Role.objects.filter(name='Administrator').first()
        manager_role = Role.objects.filter(name='Manager').first()
        cashier_role = Role.objects.filter(name='Cashier').first()
        
        # 1. Create Users
        if not options['skip_users']:
            self.create_users(options['users'], superuser, admin_role, manager_role, cashier_role)
        
        # 2. Create Customers
        if not options['skip_customers']:
            self.create_customers(options['customers'], superuser, branch)
        
        # 3. Create Products, Categories, and Variants
        if not options['skip_products']:
            self.create_products_and_categories(options['products'])
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('DATA POPULATION COMPLETE!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'  Users: {User.objects.count()}')
        self.stdout.write(f'  Customers: {Customer.objects.count()}')
        self.stdout.write(f'  Categories: {Category.objects.count()}')
        self.stdout.write(f'  Products: {Product.objects.count()}')
        self.stdout.write(f'  Product Variants: {ProductVariant.objects.count()}')

    def create_users(self, count, superuser, admin_role, manager_role, cashier_role):
        """Create users with profiles"""
        self.stdout.write(f'\n1. Creating {count} users...')
        
        roles = ['cashier', 'manager', 'admin']
        role_objects = {
            'cashier': cashier_role,
            'manager': manager_role,
            'admin': admin_role,
        }
        
        created = 0
        for i in range(count):
            try:
                # Generate user data
                if self.fake:
                    username = f"{self.fake.user_name()}{i}"
                    email = self.fake.email()
                    first_name = self.fake.first_name()
                    last_name = self.fake.last_name()
                    phone = self.fake.phone_number()[:20]
                else:
                    username = f"user{i+1:03d}"
                    email = f"user{i+1}@example.com"
                    first_name = f"First{i+1}"
                    last_name = f"Last{i+1}"
                    phone = f"2547{random.randint(10000000, 99999999)}"
                
                # Create user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    is_active=random.choice([True, True, True, False]),  # 75% active
                    is_staff=random.choice([False, False, True]),  # 33% staff
                )
                
                # Create profile
                role = random.choice(roles)
                profile = UserProfile.objects.create(
                    user=user,
                    role=role,
                    custom_role=role_objects.get(role),
                    phone_number=phone,
                    is_active=user.is_active,
                    created_by=superuser
                )
                
                created += 1
                if (i + 1) % 20 == 0:
                    self.stdout.write(f'  Created {i + 1}/{count} users...')
            except Exception as e:
                if 'UNIQUE constraint' not in str(e):
                    self.stdout.write(self.style.ERROR(f'  Error creating user {i+1}: {str(e)[:50]}'))
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created} users'))

    def create_customers(self, count, superuser, branch):
        """Create customers"""
        self.stdout.write(f'\n2. Creating {count} customers...')
        
        customer_types = ['individual', 'business']
        cities = ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret', 'Thika', 'Malindi', 'Kitale']
        countries = ['Kenya', 'Kenya', 'Kenya', 'Tanzania', 'Uganda']  # Mostly Kenya
        
        created = 0
        for i in range(count):
            try:
                if self.fake:
                    name = self.fake.company() if random.choice([True, False]) else self.fake.name()
                    email = self.fake.email()
                    phone = self.fake.phone_number()[:20]
                    address = self.fake.address()
                    city = random.choice(cities)
                    country = random.choice(countries)
                    tax_id = self.fake.bothify(text='??#######') if random.choice([True, False]) else ''
                else:
                    customer_type = random.choice(customer_types)
                    if customer_type == 'business':
                        name = f"Business {i+1} Ltd"
                    else:
                        name = f"Customer {i+1}"
                    email = f"customer{i+1}@example.com"
                    phone = f"2547{random.randint(10000000, 99999999)}"
                    address = f"Address {i+1}, Street {random.randint(1, 100)}"
                    city = random.choice(cities)
                    country = random.choice(countries)
                    tax_id = f"TAX{random.randint(100000, 999999)}" if random.choice([True, False]) else ''
                
                customer = Customer.objects.create(
                    name=name,
                    customer_type=random.choice(customer_types),
                    email=email,
                    phone=phone,
                    address=address,
                    city=city,
                    country=country,
                    tax_id=tax_id,
                    is_active=random.choice([True, True, True, False]),  # 75% active
                    created_by=superuser,
                    branch=branch if random.choice([True, False]) else None  # 50% have branch
                )
                
                created += 1
                if (i + 1) % 20 == 0:
                    self.stdout.write(f'  Created {i + 1}/{count} customers...')
            except Exception as e:
                if 'UNIQUE constraint' not in str(e):
                    self.stdout.write(self.style.ERROR(f'  Error creating customer {i+1}: {str(e)[:50]}'))
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created} customers'))

    def create_products_and_categories(self, count):
        """Create products, categories, sizes, colors, and variants"""
        self.stdout.write(f'\n3. Creating products, categories, and variants...')
        
        # Create sizes
        self.stdout.write('  Creating sizes...')
        sizes_data = [
            {'name': 'Small', 'code': 'S', 'order': 1},
            {'name': 'Medium', 'code': 'M', 'order': 2},
            {'name': 'Large', 'code': 'L', 'order': 3},
            {'name': 'Extra Large', 'code': 'XL', 'order': 4},
            {'name': 'XXL', 'code': 'XXL', 'order': 5},
            {'name': 'One Size', 'code': 'OS', 'order': 6},
        ]
        sizes = {}
        for size_data in sizes_data:
            size, created = Size.objects.get_or_create(
                code=size_data['code'],
                defaults={
                    'name': size_data['name'],
                    'display_order': size_data['order'],
                    'is_active': True
                }
            )
            sizes[size_data['code']] = size
        
        # Create colors
        self.stdout.write('  Creating colors...')
        colors_data = [
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
            {'name': 'Orange', 'hex': '#FFA500'},
            {'name': 'Purple', 'hex': '#800080'},
            {'name': 'Pink', 'hex': '#FFC0CB'},
        ]
        colors = {}
        for color_data in colors_data:
            color, created = Color.objects.get_or_create(
                name=color_data['name'],
                defaults={
                    'hex_code': color_data['hex'],
                    'is_active': True
                }
            )
            colors[color_data['name']] = color
        
        # Create main categories
        self.stdout.write('  Creating categories...')
        main_categories_data = [
            {'name': 'Electronics', 'description': 'Electronic products and gadgets'},
            {'name': 'Clothing & Apparel', 'description': 'Clothing, shoes, and accessories'},
            {'name': 'Food & Beverages', 'description': 'Food items and drinks'},
            {'name': 'Home & Kitchen', 'description': 'Home and kitchen products'},
            {'name': 'Sports & Outdoors', 'description': 'Sports equipment and outdoor gear'},
            {'name': 'Beauty & Personal Care', 'description': 'Beauty and personal care products'},
            {'name': 'Books & Media', 'description': 'Books, movies, and media'},
            {'name': 'Toys & Games', 'description': 'Toys and games for all ages'},
            {'name': 'Automotive', 'description': 'Automotive parts and accessories'},
            {'name': 'Health & Wellness', 'description': 'Health and wellness products'},
        ]
        
        main_categories = {}
        for cat_data in main_categories_data:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'is_active': True
                }
            )
            main_categories[cat_data['name']] = category
        
        # Create subcategories for each main category
        subcategories_data = {
            'Electronics': ['Smartphones', 'Laptops', 'Tablets', 'Headphones', 'Speakers', 'Cameras', 'TVs', 'Gaming Consoles'],
            'Clothing & Apparel': ['Men\'s Clothing', 'Women\'s Clothing', 'Kids\' Clothing', 'Shoes', 'Accessories', 'Bags', 'Jewelry'],
            'Food & Beverages': ['Snacks', 'Beverages', 'Dairy', 'Meat', 'Fruits', 'Vegetables', 'Bakery', 'Frozen Foods'],
            'Home & Kitchen': ['Furniture', 'Kitchenware', 'Bedding', 'Bath', 'Decor', 'Storage', 'Lighting', 'Appliances'],
            'Sports & Outdoors': ['Fitness', 'Outdoor Gear', 'Sports Equipment', 'Camping', 'Cycling', 'Water Sports'],
            'Beauty & Personal Care': ['Skincare', 'Haircare', 'Makeup', 'Fragrances', 'Personal Hygiene', 'Men\'s Grooming'],
            'Books & Media': ['Fiction', 'Non-Fiction', 'Educational', 'Children\'s Books', 'Movies', 'Music'],
            'Toys & Games': ['Action Figures', 'Board Games', 'Puzzles', 'Educational Toys', 'Outdoor Toys', 'Video Games'],
            'Automotive': ['Car Parts', 'Accessories', 'Tools', 'Maintenance', 'Tires', 'Batteries'],
            'Health & Wellness': ['Vitamins', 'Supplements', 'Medical Supplies', 'Fitness Equipment', 'Wellness Products'],
        }
        
        all_subcategories = []
        for main_cat_name, subcat_names in subcategories_data.items():
            main_cat = main_categories[main_cat_name]
            for subcat_name in subcat_names:
                subcat, created = Category.objects.get_or_create(
                    name=subcat_name,
                    defaults={
                        'parent': main_cat,
                        'description': f'{subcat_name} under {main_cat_name}',
                        'is_active': True
                    }
                )
                all_subcategories.append(subcat)
        
        self.stdout.write(f'  ✓ Created {len(main_categories)} main categories and {len(all_subcategories)} subcategories')
        
        # Product name templates by category
        product_templates = {
            'Electronics': ['Smartphone', 'Laptop', 'Tablet', 'Headphones', 'Speaker', 'Camera', 'TV', 'Gaming Console', 'Smart Watch', 'Earbuds'],
            'Clothing & Apparel': ['T-Shirt', 'Jeans', 'Dress', 'Shirt', 'Jacket', 'Shoes', 'Hat', 'Bag', 'Belt', 'Watch'],
            'Food & Beverages': ['Snack Pack', 'Soft Drink', 'Juice', 'Milk', 'Cheese', 'Bread', 'Cereal', 'Chips', 'Candy', 'Water'],
            'Home & Kitchen': ['Chair', 'Table', 'Sofa', 'Bed', 'Lamp', 'Vase', 'Plate', 'Cup', 'Pan', 'Towel'],
            'Sports & Outdoors': ['Dumbbell', 'Yoga Mat', 'Basketball', 'Tent', 'Backpack', 'Bicycle', 'Running Shoes', 'Swimming Goggles'],
            'Beauty & Personal Care': ['Shampoo', 'Conditioner', 'Lotion', 'Perfume', 'Lipstick', 'Foundation', 'Soap', 'Toothpaste'],
            'Books & Media': ['Novel', 'Textbook', 'Cookbook', 'DVD', 'CD', 'Magazine', 'Comic Book', 'Dictionary'],
            'Toys & Games': ['Action Figure', 'Board Game', 'Puzzle', 'Doll', 'Car Toy', 'Building Blocks', 'Card Game'],
            'Automotive': ['Car Battery', 'Tire', 'Oil Filter', 'Brake Pad', 'Headlight', 'Mirror', 'Wiper', 'Air Freshener'],
            'Health & Wellness': ['Vitamin', 'Protein Powder', 'Bandage', 'Thermometer', 'First Aid Kit', 'Massage Oil'],
        }
        
        # Generate products
        self.stdout.write(f'  Creating {count} products...')
        products_per_category = count // len(all_subcategories) if all_subcategories else count // 10
        if products_per_category < 1:
            products_per_category = 1
        
        created_products = 0
        created_variants = 0
        
        for subcat in all_subcategories:
            main_cat = subcat.parent or subcat
            main_cat_name = main_cat.name
            
            # Get templates for this category
            templates = product_templates.get(main_cat_name, ['Product'])
            
            for i in range(products_per_category):
                if created_products >= count:
                    break
                
                try:
                    # Generate product name
                    template = random.choice(templates)
                    variations = ['Standard', 'Premium', 'Deluxe', 'Economy', 'Pro', 'Elite', 'Basic', 'Advanced']
                    if i < len(templates):
                        product_name = f"{template} {i+1}"
                    else:
                        variation = random.choice(variations)
                        product_name = f"{template} {variation} {i+1}"
                    
                    # Generate pricing
                    cost = Decimal(str(round(random.uniform(50, 5000), 2)))
                    markup = Decimal(str(round(random.uniform(1.2, 3.0), 2)))  # 20% to 200% markup
                    price = cost * markup
                    
                    # Generate stock data
                    stock = random.randint(0, 500)
                    low_stock_threshold = random.randint(10, 100)
                    
                    # Generate SKU
                    sku = f"PRD-{main_cat_name[:3].upper()}-{str(created_products+1).zfill(6)}"
                    
                    # Generate barcode
                    barcode = f"{random.randint(100000000000, 999999999999)}"
                    while Product.objects.filter(barcode=barcode).exists():
                        barcode = f"{random.randint(100000000000, 999999999999)}"
                    
                    # Determine if product has variants
                    has_variants = random.choice([True, True, False])  # 66% have variants
                    
                    # Create product
                    product = Product.objects.create(
                        name=product_name,
                        sku=sku,
                        barcode=barcode,
                        category=main_cat,
                        subcategory=subcat if subcat.parent else None,
                        price=price,
                        cost=cost,
                        stock_quantity=stock,
                        low_stock_threshold=low_stock_threshold,
                        reorder_quantity=random.randint(50, 200),
                        unit=random.choice(['piece', 'kg', 'box', 'pack', 'bottle']),
                        description=f"{product_name} - High quality product in {subcat.name} category.",
                        supplier=f"Supplier {random.randint(1, 20)}",
                        tax_rate=Decimal(str(round(random.uniform(0, 16), 2))),
                        is_taxable=random.choice([True, True, False]),
                        track_stock=True,
                        has_variants=has_variants,
                        is_active=random.choice([True, True, True, False]),  # 75% active
                    )
                    
                    # Add variants if product has variants
                    if has_variants:
                        use_colors = random.choice([True, True, False])  # 66% use colors
                        use_sizes = random.choice([True, True, False])  # 66% use sizes
                        
                        if use_colors:
                            selected_colors = random.sample(list(colors.values()), k=min(random.randint(2, 8), len(colors)))
                            product.available_colors.set(selected_colors)
                        
                        if use_sizes:
                            selected_sizes = random.sample(list(sizes.values()), k=min(random.randint(2, 5), len(sizes)))
                            product.available_sizes.set(selected_sizes)
                        
                        # Create variants
                        variant_count = 0
                        if use_sizes and use_colors and product.available_sizes.exists() and product.available_colors.exists():
                            # Size + Color combinations
                            for size in product.available_sizes.all():
                                for color in product.available_colors.all():
                                    variant_price = price * Decimal(str(round(random.uniform(0.9, 1.2), 2)))
                                    variant_cost = cost * Decimal(str(round(random.uniform(0.9, 1.1), 2)))
                                    variant_stock = random.randint(0, 200)
                                    
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
                                    created_variants += 1
                        
                        elif use_colors and product.available_colors.exists():
                            # Color only
                            for color in product.available_colors.all():
                                variant_price = price * Decimal(str(round(random.uniform(0.9, 1.2), 2)))
                                variant_cost = cost * Decimal(str(round(random.uniform(0.9, 1.1), 2)))
                                variant_stock = random.randint(0, 200)
                                
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
                                created_variants += 1
                        
                        elif use_sizes and product.available_sizes.exists():
                            # Size only
                            for size in product.available_sizes.all():
                                variant_price = price * Decimal(str(round(random.uniform(0.9, 1.2), 2)))
                                variant_cost = cost * Decimal(str(round(random.uniform(0.9, 1.1), 2)))
                                variant_stock = random.randint(0, 200)
                                
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
                                created_variants += 1
                    
                    created_products += 1
                    if created_products % 100 == 0:
                        self.stdout.write(f'    Created {created_products}/{count} products...')
                
                except Exception as e:
                    if 'UNIQUE constraint' not in str(e):
                        self.stdout.write(self.style.ERROR(f'    Error creating product: {str(e)[:50]}'))
            
            if created_products >= count:
                break
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_products} products'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_variants} product variants'))
