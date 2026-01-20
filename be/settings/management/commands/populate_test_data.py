"""
Management command to populate database with test data:
- 1 Tenant (Business/Company)
- 20 users
- 100 customers
- 1000 products with categories and variants
Note: Branches are NOT created by default - they should be added through module settings
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile, Role
from sales.models import Customer, Sale, SaleItem, Invoice, InvoiceItem, Payment, PaymentPlan
from products.models import Category, Product, Size, Color, ProductVariant
from settings.models import Tenant, Branch
from suppliers.models import Supplier
from expenses.models import Expense, ExpenseCategory
from inventory.models import StockMovement
from django.utils import timezone
from decimal import Decimal
import random
import uuid
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Try to use Faker if available, otherwise use manual data
try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False


class Command(BaseCommand):
    help = 'Populate database with test data: 1 tenant, 20 users, 100 customers, 1000 products with variants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=20,
            help='Number of users to create (default: 20)',
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
            '--skip-tenant',
            action='store_true',
            help='Skip tenant creation',
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
        parser.add_argument(
            '--sales',
            type=int,
            default=0,
            help='Number of sales to create (default: 0)',
        )
        parser.add_argument(
            '--expenses',
            type=int,
            default=0,
            help='Number of expenses to create (default: 0)',
        )
        parser.add_argument(
            '--skip-sales',
            action='store_true',
            help='Skip sales creation',
        )
        parser.add_argument(
            '--skip-expenses',
            action='store_true',
            help='Skip expense creation',
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
                'Faker library not available. Using simple data generation.'
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
            logger.info(f"Created superuser: {superuser.username}")
        
        # Get roles
        admin_role = Role.objects.filter(name='Administrator').first()
        manager_role = Role.objects.filter(name='Manager').first()
        cashier_role = Role.objects.filter(name='Cashier').first()
        
        # 0. Create Tenant (Business/Company)
        tenant = None
        if not options['skip_tenant']:
            tenant = self.create_tenant(superuser)
        
        # 1. Create Users
        if not options['skip_users']:
            self.create_users(options['users'], superuser, admin_role, manager_role, cashier_role, tenant)
        
        # 2. Create Customers (no branch by default - branches added through module settings)
        if not options['skip_customers']:
            self.create_customers(options['customers'], superuser, tenant)
        
        # 3. Create Products, Categories, and Variants
        if not options['skip_products']:
            self.create_products_and_categories(options['products'])
        
        # 4. Create Sales, Invoices, Payments, and Stock Movements
        created_sales_list = []
        if not options['skip_sales'] and options['sales'] > 0:
            products = list(Product.objects.filter(is_active=True))
            customers = list(Customer.objects.all())
            branch = Branch.objects.first()
            if not branch:
                # Create default branch if none exists
                tenant = Tenant.objects.first()
                if tenant:
                    branch = Branch.objects.create(
                        tenant=tenant,
                        name='Headquarters',
                        code='HQ',
                        address='Nairobi, Kenya',
                        phone='+254700000000',
                        is_active=True
                    )
                    self.stdout.write('  Created default branch: Headquarters')
            
            if products and customers and branch:
                created_sales_list = self.create_sales(options['sales'], products, customers, superuser, branch)
            else:
                missing = []
                if not products:
                    missing.append('products')
                if not customers:
                    missing.append('customers')
                if not branch:
                    missing.append('branch')
                self.stdout.write(self.style.WARNING(f'  ⚠ Skipping sales: Missing {", ".join(missing)}'))
        
        # 5. Create Expenses (sofa-making related)
        created_expenses = []
        if not options['skip_expenses'] and options['expenses'] > 0:
            created_expenses = self.create_expenses(options['expenses'], superuser)
        
        # 6. Create Accounting Journal Entries for sales and expenses
        if created_sales_list or created_expenses:
            self.create_accounting_entries(created_sales_list, created_expenses, superuser)
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('DATA POPULATION COMPLETE!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'  Tenants: {Tenant.objects.count()}')
        self.stdout.write(f'  Branches: {Branch.objects.count()} (add branches through module settings)')
        self.stdout.write(f'  Users: {User.objects.count()}')
        self.stdout.write(f'  Customers: {Customer.objects.count()}')
        self.stdout.write(f'  Categories: {Category.objects.count()}')
        self.stdout.write(f'  Products: {Product.objects.count()}')
        self.stdout.write(f'  Product Variants: {ProductVariant.objects.count()}')
        self.stdout.write(f'  Sales: {Sale.objects.count()}')
        self.stdout.write(f'  Invoices: {Invoice.objects.count()}')
        self.stdout.write(f'  Payments: {Payment.objects.count()}')
        self.stdout.write(f'  Stock Movements: {StockMovement.objects.count()}')
        self.stdout.write(f'  Expenses: {Expense.objects.count()}')
        from accounting.models import Transaction, JournalEntry
        self.stdout.write(f'  Transactions: {Transaction.objects.count()}')
        self.stdout.write(f'  Journal Entries: {JournalEntry.objects.count()}')
        logger.info("Data population completed successfully")
    
    def create_tenant(self, superuser):
        """Create a default tenant (Business/Company)"""
        self.stdout.write('\n0. Creating tenant (Business/Company)...')
        
        tenant, created = Tenant.objects.get_or_create(
            code='TENANT001',
            defaults={
                'name': 'CompleteByte Business',
                'registration_number': 'REG-001-2024',
                'tax_id': 'TAX-001-2024',
                'address': '123 Business Street',
                'city': 'Nairobi',
                'country': 'Kenya',
                'phone': '+254700000000',
                'email': 'info@completebyte.com',
                'website': 'https://completebyte.com',
                'is_active': True,
                'owner': superuser,
                'created_by': superuser
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created tenant: {tenant.name}'))
            logger.info(f"Created tenant: {tenant.name} (code: {tenant.code})")
        else:
            self.stdout.write(self.style.WARNING(f'  ⚠ Tenant already exists: {tenant.name}'))
            logger.info(f"Using existing tenant: {tenant.name}")
        
        return tenant

    def create_users(self, count, superuser, admin_role, manager_role, cashier_role, tenant=None):
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
                if (i + 1) % 10 == 0:
                    self.stdout.write(f'  Created {i + 1}/{count} users...')
                    logger.debug(f"Created {i + 1}/{count} users")
            except Exception as e:
                if 'UNIQUE constraint' not in str(e):
                    error_msg = f'Error creating user {i+1}: {str(e)[:50]}'
                    self.stdout.write(self.style.ERROR(f'  {error_msg}'))
                    logger.error(error_msg)
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created} users'))
        logger.info(f"Created {created} users")

    def create_customers(self, count, superuser, tenant=None):
        """Create customers (no branch by default - branches added through module settings)"""
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
                
                # Customers don't have branches by default - branches are added through module settings
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
                    branch=None  # No branch by default
                )
                
                created += 1
                if (i + 1) % 20 == 0:
                    self.stdout.write(f'  Created {i + 1}/{count} customers...')
                    logger.debug(f"Created {i + 1}/{count} customers")
            except Exception as e:
                if 'UNIQUE constraint' not in str(e):
                    error_msg = f'Error creating customer {i+1}: {str(e)[:50]}'
                    self.stdout.write(self.style.ERROR(f'  {error_msg}'))
                    logger.error(error_msg)
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created} customers'))
        logger.info(f"Created {created} customers")

    def create_products_and_categories(self, count):
        """Create products, categories, sizes, colors, and variants - SOFA MAKING PRODUCTS ONLY"""
        self.stdout.write(f'\n3. Creating sofa-making products, categories, and variants...')
        
        # First, get or create suppliers for products
        suppliers = list(Supplier.objects.all())
        if not suppliers:
            # Create some default suppliers if none exist
            self.stdout.write('  Creating default suppliers...')
            supplier_names = [
                'Fabric Suppliers Ltd', 'Foam & Cushioning Co', 'Hardware Supplies Inc',
                'Textile Manufacturers', 'Upholstery Materials Co', 'Furniture Components Ltd'
            ]
            for name in supplier_names:
                supplier, created = Supplier.objects.get_or_create(
                    name=name,
                    defaults={
                        'email': f'{name.lower().replace(" ", ".")}@example.com',
                        'phone': f'+2547{random.randint(10000000, 99999999)}',
                        'address': 'Nairobi, Kenya',
                        'created_by': User.objects.filter(is_superuser=True).first()
                    }
                )
                if created:
                    suppliers.append(supplier)
            suppliers = list(Supplier.objects.all())
        
        if not suppliers:
            self.stdout.write(self.style.WARNING('  ⚠ No suppliers available. Products will be created without suppliers.'))
        
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
        
        # Create main categories - SOFA MAKING ONLY
        self.stdout.write('  Creating sofa-making categories...')
        main_categories_data = [
            {'name': 'Sofas & Couches', 'description': 'Complete sofas and couches'},
            {'name': 'Cushions & Pillows', 'description': 'Cushions, pillows, and padding'},
            {'name': 'Curtains & Drapes', 'description': 'Window treatments and curtains'},
            {'name': 'Cushion Covers', 'description': 'Cushion covers and fabric covers'},
            {'name': 'Fabric & Upholstery', 'description': 'Fabric, upholstery materials, and textiles'},
            {'name': 'Foam & Cushioning', 'description': 'Foam, cushioning materials, and padding'},
            {'name': 'Furniture Hardware', 'description': 'Legs, springs, screws, and furniture hardware'},
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
        
        # Create subcategories for each main category - SOFA MAKING ONLY
        subcategories_data = {
            'Sofas & Couches': ['3-Seater Sofas', '2-Seater Sofas', 'Corner Sofas', 'Sofa Beds', 'Recliner Sofas', 'Modular Sofas', 'Chaise Lounges'],
            'Cushions & Pillows': ['Throw Pillows', 'Back Cushions', 'Seat Cushions', 'Decorative Pillows', 'Bolster Pillows', 'Floor Cushions'],
            'Curtains & Drapes': ['Ready-Made Curtains', 'Custom Curtains', 'Curtain Fabric', 'Curtain Rods', 'Curtain Rings', 'Valances'],
            'Cushion Covers': ['Zipper Covers', 'Button Covers', 'Velcro Covers', 'Removable Covers', 'Decorative Covers'],
            'Fabric & Upholstery': ['Upholstery Fabric', 'Leather', 'Suede', 'Velvet', 'Cotton Fabric', 'Linen Fabric', 'Polyester Fabric', 'Chenille'],
            'Foam & Cushioning': ['High-Density Foam', 'Memory Foam', 'Polyurethane Foam', 'Feather Filling', 'Fiber Filling', 'Spring Units'],
            'Furniture Hardware': ['Sofa Legs', 'Springs', 'Screws & Bolts', 'Corner Braces', 'Furniture Glides', 'Casters', 'Drawer Slides'],
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
        
        # Product name templates by category - SOFA MAKING ONLY
        product_templates = {
            'Sofas & Couches': ['3-Seater Sofa', '2-Seater Sofa', 'Corner Sofa', 'Sofa Bed', 'Recliner Sofa', 'Modular Sofa', 'Chaise Lounge', 'Sectional Sofa'],
            'Cushions & Pillows': ['Throw Pillow', 'Back Cushion', 'Seat Cushion', 'Decorative Pillow', 'Bolster Pillow', 'Floor Cushion', 'Lumbar Pillow'],
            'Curtains & Drapes': ['Ready-Made Curtain', 'Custom Curtain', 'Curtain Fabric', 'Curtain Rod', 'Curtain Ring', 'Valance', 'Curtain Tieback'],
            'Cushion Covers': ['Zipper Cover', 'Button Cover', 'Velcro Cover', 'Removable Cover', 'Decorative Cover', 'Washable Cover'],
            'Fabric & Upholstery': ['Upholstery Fabric', 'Leather', 'Suede', 'Velvet', 'Cotton Fabric', 'Linen Fabric', 'Polyester Fabric', 'Chenille', 'Microfiber'],
            'Foam & Cushioning': ['High-Density Foam', 'Memory Foam', 'Polyurethane Foam', 'Feather Filling', 'Fiber Filling', 'Spring Unit', 'Foam Sheet'],
            'Furniture Hardware': ['Sofa Leg', 'Spring', 'Screw & Bolt', 'Corner Brace', 'Furniture Glide', 'Caster', 'Drawer Slide', 'Bracket'],
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
                        description=f"{product_name} - High quality sofa-making product in {subcat.name} category.",
                        supplier=random.choice(suppliers) if suppliers else None,
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
    
    def create_sales(self, count, products, customers, superuser, branch):
        """Create sales with invoices, payments, and stock movements - SOFA PRODUCTS ONLY"""
        self.stdout.write(f'\n4. Creating {count} sales with invoices and stock movements...')
        
        if not products:
            self.stdout.write(self.style.WARNING('  ⚠ No products available. Skipping sales creation.'))
            return
        
        if not customers:
            self.stdout.write(self.style.WARNING('  ⚠ No customers available. Skipping sales creation.'))
            return
        
        created_sales = 0
        created_invoices = 0
        created_payments = 0
        created_stock_movements = 0
        created_sales_list = []
        
        # Filter to only sofa-making products
        sofa_products = [p for p in products if p.category and any(
            cat in p.category.name for cat in ['Sofa', 'Cushion', 'Curtain', 'Fabric', 'Foam', 'Hardware']
        )]
        if not sofa_products:
            sofa_products = products  # Fallback to all products if no sofa categories found
        
        payment_statuses = ['fully_paid', 'partial', 'unpaid']
        
        for i in range(count):
            try:
                customer = random.choice(customers)
                sale_type = random.choice(['pos', 'normal'])
                payment_status = random.choice(payment_statuses)
                
                # Create sale items (1-4 items per sale)
                num_items = random.randint(1, 4)
                sale_items = []
                subtotal = Decimal('0')
                
                for _ in range(num_items):
                    product = random.choice(sofa_products)
                    variant = None
                    
                    # Try to get a variant if product has variants
                    if product.has_variants and product.variants.exists():
                        variant = random.choice(list(product.variants.all()))
                        unit_price = variant.effective_price
                        available_stock = variant.stock_quantity
                    else:
                        unit_price = product.price
                        available_stock = product.stock_quantity
                    
                    # Quantity should not exceed available stock
                    max_quantity = min(5, available_stock) if available_stock > 0 else 1
                    quantity = random.randint(1, max_quantity)
                    item_subtotal = Decimal(quantity) * unit_price
                    subtotal += item_subtotal
                    
                    sale_items.append({
                        'product': product,
                        'variant': variant,
                        'quantity': quantity,
                        'unit_price': unit_price,
                        'subtotal': item_subtotal
                    })
                
                # Calculate totals
                tax_rate = Decimal('0.16')  # 16% VAT
                tax_amount = subtotal * tax_rate
                discount_amount = Decimal('0') if random.random() > 0.2 else subtotal * Decimal(str(random.uniform(0.05, 0.15)))
                total = subtotal + tax_amount - discount_amount
                
                # Create sale (Sale model doesn't have customer field - customer is linked via Invoice)
                sale = Sale.objects.create(
                    sale_type=sale_type,
                    branch=branch,
                    cashier=superuser,
                    subtotal=subtotal,
                    tax_amount=tax_amount,
                    discount_amount=discount_amount,
                    total=total,
                    payment_method=random.choice(['cash', 'mpesa', 'other']),
                    amount_paid=Decimal('0'),  # Will be set based on payment status
                    change=Decimal('0'),
                    notes=f"Sofa-making sale {i+1} - {payment_status}"
                )
                
                # Create sale items and stock movements
                for item_data in sale_items:
                    SaleItem.objects.create(
                        sale=sale,
                        product=item_data['product'],
                        variant=item_data['variant'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        subtotal=item_data['subtotal']
                    )
                    
                    # Get unit cost for stock movement
                    if item_data['variant']:
                        unit_cost = item_data['variant'].effective_cost
                    else:
                        unit_cost = item_data['product'].cost
                    
                    # Create stock movement (sale - the save() method will handle stock update)
                    StockMovement.objects.create(
                        branch=branch,
                        product=item_data['product'],
                        variant=item_data['variant'],
                        movement_type='sale',
                        quantity=item_data['quantity'],  # Positive quantity - save() method handles the subtraction
                        unit_cost=unit_cost,
                        total_cost=item_data['quantity'] * unit_cost,
                        reference=sale.sale_number,
                        user=superuser,
                        notes=f'Sale {sale.sale_number} - {item_data["product"].name}'
                    )
                    created_stock_movements += 1
                
                # Create invoice for normal sales
                invoice = None
                if sale_type == 'normal':
                    invoice = Invoice.objects.create(
                        sale=sale,
                        branch=branch,
                        customer=customer,
                        customer_name=customer.name,
                        customer_email=customer.email or '',
                        customer_phone=customer.phone or '',
                        subtotal=subtotal,
                        tax_amount=tax_amount,
                        discount_amount=discount_amount,
                        total=total,
                        amount_paid=Decimal('0'),
                        balance=total,
                        status='sent',
                        due_date=timezone.now().date() + timedelta(days=random.randint(7, 90)),
                        issued_date=timezone.now().date() - timedelta(days=random.randint(0, 30)),
                        created_by=superuser
                    )
                    created_invoices += 1
                    
                    # Create invoice items
                    for item_data in sale_items:
                        InvoiceItem.objects.create(
                            invoice=invoice,
                            product=item_data['product'],
                            variant=item_data['variant'],
                            quantity=item_data['quantity'],
                            unit_price=item_data['unit_price'],
                            subtotal=item_data['subtotal']
                        )
                
                # Handle payment status
                if payment_status == 'fully_paid':
                    if sale_type == 'pos':
                        sale.amount_paid = total
                        sale.save()
                    elif invoice:
                        # Full payment for invoice
                        Payment.objects.create(
                            invoice=invoice,
                            amount=total,
                            payment_method=random.choice(['cash', 'mpesa', 'bank_transfer']),
                            payment_date=timezone.now().date() - timedelta(days=random.randint(0, 5)),
                            recorded_by=superuser,
                            notes='Full payment'
                        )
                        created_payments += 1
                
                elif payment_status == 'partial' and invoice:
                    # Partial payment (30-70% of total)
                    partial_amount = total * Decimal(str(random.uniform(0.3, 0.7)))
                    Payment.objects.create(
                        invoice=invoice,
                        amount=partial_amount,
                        payment_method=random.choice(['cash', 'mpesa', 'bank_transfer']),
                        payment_date=timezone.now().date() - timedelta(days=random.randint(0, 10)),
                        recorded_by=superuser,
                        notes='Partial payment'
                    )
                    created_payments += 1
                
                created_sales += 1
                created_sales_list.append(sale)
                if (i + 1) % 20 == 0:
                    self.stdout.write(f'    Created {i + 1}/{count} sales...')
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    Error creating sale {i+1}: {str(e)[:100]}'))
                logger.error(f"Error creating sale: {e}")
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_sales} sales'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_invoices} invoices'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_payments} payments'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_stock_movements} stock movements'))
        return created_sales_list
    
    def create_expenses(self, count, superuser):
        """Create expenses - SOFA MAKING RELATED ONLY"""
        self.stdout.write(f'\n5. Creating {count} sofa-making related expenses...')
        
        # Get expense categories (sofa-making related)
        categories = ExpenseCategory.objects.filter(
            name__icontains='raw material'
        ) | ExpenseCategory.objects.filter(
            name__icontains='equipment'
        ) | ExpenseCategory.objects.filter(
            name__icontains='fabric'
        ) | ExpenseCategory.objects.filter(
            name__icontains='foam'
        ) | ExpenseCategory.objects.filter(
            name__icontains='hardware'
        ) | ExpenseCategory.objects.filter(
            name__icontains='supplies'
        )
        
        if not categories.exists():
            # Use any available categories
            categories = ExpenseCategory.objects.all()[:5]
        
        if not categories.exists():
            self.stdout.write(self.style.WARNING('  ⚠ No expense categories available. Creating default categories...'))
            # Create sofa-making expense categories
            sofa_categories = [
                'Fabric & Upholstery Materials',
                'Foam & Cushioning Materials',
                'Furniture Hardware',
                'Tools & Equipment',
                'Raw Materials',
                'Packaging Materials',
                'Transportation',
                'Utilities'
            ]
            for cat_name in sofa_categories:
                ExpenseCategory.objects.get_or_create(
                    name=cat_name,
                    defaults={'description': f'{cat_name} for sofa-making business'}
                )
            categories = ExpenseCategory.objects.all()
        
        created = 0
        created_expenses = []
        expense_types = ['fabric_purchase', 'foam_purchase', 'hardware_purchase', 'tool_purchase', 'transport', 'utilities']
        expense_descriptions = {
            'fabric_purchase': ['Upholstery fabric purchase', 'Leather material', 'Suede fabric', 'Velvet fabric', 'Cotton fabric'],
            'foam_purchase': ['High-density foam', 'Memory foam sheets', 'Polyurethane foam', 'Feather filling', 'Fiber filling'],
            'hardware_purchase': ['Sofa legs', 'Springs', 'Screws and bolts', 'Corner braces', 'Furniture glides'],
            'tool_purchase': ['Sewing machine maintenance', 'Cutting tools', 'Stapling gun', 'Measuring tools'],
            'transport': ['Fabric delivery', 'Material transportation', 'Customer delivery'],
            'utilities': ['Electricity bill', 'Water bill', 'Workshop rent']
        }
        
        for i in range(count):
            try:
                category = random.choice(list(categories))
                expense_type = random.choice(expense_types)
                descriptions = expense_descriptions.get(expense_type, ['Sofa-making expense'])
                description = random.choice(descriptions)
                
                amount = Decimal(str(round(random.uniform(500, 50000), 2)))
                expense_date = timezone.now().date() - timedelta(days=random.randint(0, 90))
                
                branch = Branch.objects.first()
                expense = Expense.objects.create(
                    branch=branch,
                    category=category,
                    amount=amount,
                    description=description,
                    expense_date=expense_date,
                    payment_method=random.choice(['cash', 'mpesa', 'bank', 'card', 'other']),
                    vendor=random.choice(['Fabric Suppliers Ltd', 'Foam & Cushioning Co', 'Hardware Supplies Inc', 'Local Vendor']),
                    receipt_number=f'RCP-{str(i+1).zfill(6)}' if random.choice([True, False]) else '',
                    notes=f'Sofa-making business expense - {description}',
                    created_by=superuser,
                    status=random.choice(['approved', 'pending', 'paid'])
                )
                
                created += 1
                created_expenses.append(expense)
                if (i + 1) % 10 == 0:
                    self.stdout.write(f'    Created {i + 1}/{count} expenses...')
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    Error creating expense {i+1}: {str(e)[:100]}'))
                logger.error(f"Error creating expense: {e}")
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created} expenses'))
        return created_expenses
    
    def create_accounting_entries(self, sales, expenses, superuser):
        """Create journal entries for sales and expenses to match accounting data"""
        self.stdout.write(f'\n6. Creating accounting journal entries for sales and expenses...')
        
        from accounting.services import create_sale_journal_entry, create_expense_journal_entry
        from accounting.models import Transaction, JournalEntry
        
        created_transactions = 0
        created_entries = 0
        
        # Create journal entries for sales
        for sale in sales:
            try:
                txn = create_sale_journal_entry(sale)
                created_transactions += 1
                created_entries += txn.journal_entries.count()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'    Warning: Could not create journal entry for sale {sale.sale_number}: {str(e)[:50]}'))
        
        # Create journal entries for expenses
        for expense in expenses:
            try:
                txn = create_expense_journal_entry(expense)
                created_transactions += 1
                created_entries += txn.journal_entries.count()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'    Warning: Could not create journal entry for expense {expense.expense_number}: {str(e)[:50]}'))
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_transactions} transactions'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_entries} journal entries'))
