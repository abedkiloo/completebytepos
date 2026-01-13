"""
Comprehensive data generation script for soft furnishings business
Generates: Users, Products (soft furnishings), Customers, Sales (with installments), Expenses
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta
import random
import uuid

from accounts.models import UserProfile, Role
from products.models import Category, Product, Size, Color, ProductVariant
from sales.models import Customer, Sale, SaleItem, Invoice, InvoiceItem, Payment, PaymentPlan
from expenses.models import Expense, ExpenseCategory
from inventory.models import StockMovement
from settings.models import Branch, Tenant

# Try to use Faker if available, otherwise use manual data
try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False


class Command(BaseCommand):
    help = 'Populate database with comprehensive soft furnishings data: users, products, customers, sales, installments, expenses'

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
            default=50,
            help='Number of customers to create (default: 50)',
        )
        parser.add_argument(
            '--products',
            type=int,
            default=200,
            help='Number of products to create (default: 200)',
        )
        parser.add_argument(
            '--sales',
            type=int,
            default=100,
            help='Number of sales to create (default: 100)',
        )
        parser.add_argument(
            '--expenses',
            type=int,
            default=30,
            help='Number of expenses to create (default: 30)',
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
            '--skip-sales',
            action='store_true',
            help='Skip sales creation',
        )
        parser.add_argument(
            '--skip-expenses',
            action='store_true',
            help='Skip expenses creation',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('POPULATING SOFT FURNISHINGS DATA'))
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
        
        # Get or create superuser
        superuser = User.objects.filter(is_superuser=True).first()
        if not superuser:
            superuser = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin'
            )
            self.stdout.write(self.style.SUCCESS('Created admin superuser'))
        
        # Get or create tenant and branch
        tenant = Tenant.objects.first()
        if not tenant:
            tenant = Tenant.objects.create(
                name='CompleteByte Business',
                code='DEFAULT',
                country='Kenya',
                owner=superuser,
                created_by=superuser
            )
        
        branch = Branch.objects.filter(is_headquarters=True).first()
        if not branch:
            branch = Branch.objects.create(
                tenant=tenant,
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
        
        # 2. Create Products (Soft Furnishings)
        products = []
        if not options['skip_products']:
            products = self.create_soft_furnishings_products(options['products'], superuser, branch)
        
        # 3. Create Customers
        customers = []
        if not options['skip_customers']:
            customers = self.create_customers(options['customers'], superuser, branch)
        
        # 4. Create Sales with different payment statuses
        if not options['skip_sales'] and products and customers:
            self.create_sales(options['sales'], products, customers, superuser, branch)
        
        # 5. Create Expenses
        if not options['skip_expenses']:
            self.create_expenses(options['expenses'], superuser, branch)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('DATA POPULATION COMPLETE!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'  Users: {User.objects.count()}')
        self.stdout.write(f'  Customers: {Customer.objects.count()}')
        self.stdout.write(f'  Categories: {Category.objects.count()}')
        self.stdout.write(f'  Products: {Product.objects.count()}')
        self.stdout.write(f'  Product Variants: {ProductVariant.objects.count()}')
        self.stdout.write(f'  Sales: {Sale.objects.count()}')
        self.stdout.write(f'  Invoices: {Invoice.objects.count()}')
        self.stdout.write(f'  Payments: {Payment.objects.count()}')
        self.stdout.write(f'  Payment Plans: {PaymentPlan.objects.count()}')
        self.stdout.write(f'  Expenses: {Expense.objects.count()}')
        
        # Payment status summary
        if Invoice.objects.exists():
            fully_paid = Invoice.objects.filter(status='paid').count()
            partial = Invoice.objects.filter(status='partial').count()
            unpaid = Invoice.objects.filter(status='sent').count()
            self.stdout.write(f'\nInvoice Payment Status:')
            self.stdout.write(f'  Fully Paid: {fully_paid}')
            self.stdout.write(f'  Partially Paid: {partial}')
            self.stdout.write(f'  Unpaid: {unpaid}')

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

    def create_soft_furnishings_products(self, count, superuser, branch):
        """Create soft furnishings products with variants"""
        self.stdout.write(f'\n2. Creating {count} soft furnishings products with variants...')
        
        # Soft furnishings categories
        categories_data = [
            {
                'name': 'Sofas & Couches',
                'description': 'Complete sofas and couches',
                'products': [
                    '2-Seater Sofa', '3-Seater Sofa', '4-Seater Sofa', '5-Seater Sofa',
                    'Corner Sofa', 'Sectional Sofa', 'L-Shaped Sofa', 'Chaise Lounge',
                    'Sofa Bed', 'Recliner Sofa', 'Loveseat', 'Futon'
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,
                'price_range': (50000, 500000),
            },
            {
                'name': 'Cushions & Pillows',
                'description': 'Cushions, pillows, and throw pillows',
                'products': [
                    'Square Cushion', 'Rectangular Cushion', 'Round Cushion', 'Bolster Pillow',
                    'Lumbar Pillow', 'Throw Pillow', 'Floor Cushion', 'Corner Cushion',
                    'Decorative Pillow', 'Accent Pillow', 'Wedge Pillow', 'Neck Pillow'
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,
                'price_range': (500, 15000),
            },
            {
                'name': 'Curtains & Drapes',
                'description': 'Window curtains and drapes',
                'products': [
                    'Sheer Curtains', 'Blackout Curtains', 'Thermal Curtains', 'Voile Curtains',
                    'Velvet Curtains', 'Linen Curtains', 'Cotton Curtains', 'Silk Curtains',
                    'Roman Blinds', 'Roller Blinds', 'Vertical Blinds', 'Panel Curtains'
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,
                'price_range': (2000, 50000),
            },
            {
                'name': 'Cushion Covers',
                'description': 'Covers for cushions and pillows',
                'products': [
                    'Zipper Cushion Cover', 'Envelope Cushion Cover', 'Button Cushion Cover',
                    'Velcro Cushion Cover', 'Tie Cushion Cover', 'Decorative Cushion Cover',
                    'Embroidered Cover', 'Printed Cover', 'Plain Cover', 'Patterned Cover'
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': True,
                'price_range': (300, 8000),
            },
            {
                'name': 'Fabric & Upholstery',
                'description': 'Fabrics for upholstery and decoration',
                'products': [
                    'Cotton Fabric', 'Linen Fabric', 'Polyester Fabric', 'Velvet Fabric',
                    'Suede Fabric', 'Leather Sheet', 'Microfiber Fabric', 'Chenille Fabric',
                    'Tweed Fabric', 'Canvas Fabric', 'Jacquard Fabric', 'Brocade Fabric'
                ],
                'has_variants': True,
                'use_colors': True,
                'use_sizes': False,  # Fabric sold by meter
                'price_range': (500, 10000),
            },
            {
                'name': 'Foam & Cushioning',
                'description': 'Foam and cushioning materials',
                'products': [
                    'High Density Foam', 'Medium Density Foam', 'Low Density Foam',
                    'Memory Foam', 'Rebonded Foam', 'HR Foam', 'PU Foam',
                    'Polyester Fiber', 'Polyester Fill', 'Cotton Batting', 'Feather Fill'
                ],
                'has_variants': True,
                'use_colors': False,
                'use_sizes': True,
                'price_range': (1000, 25000),
            },
        ]
        
        # Create sizes
        sizes_data = [
            {'name': 'Small (2-Seater)', 'code': 'S', 'order': 1},
            {'name': 'Medium (3-Seater)', 'code': 'M', 'order': 2},
            {'name': 'Large (4-Seater)', 'code': 'L', 'order': 3},
            {'name': 'Extra Large (5-Seater)', 'code': 'XL', 'order': 4},
            {'name': 'Sectional', 'code': 'SEC', 'order': 5},
            {'name': 'Corner Unit', 'code': 'COR', 'order': 6},
            {'name': 'One Size', 'code': 'OS', 'order': 7},
            {'name': '18x18 inches', 'code': '18x18', 'order': 8},
            {'name': '20x20 inches', 'code': '20x20', 'order': 9},
            {'name': '24x24 inches', 'code': '24x24', 'order': 10},
        ]
        sizes = {}
        for size_data in sizes_data:
            size, _ = Size.objects.get_or_create(
                code=size_data['code'],
                defaults={'name': size_data['name'], 'display_order': size_data['order'], 'is_active': True}
            )
            sizes[size_data['code']] = size
        
        # Create colors
        colors_data = [
            {'name': 'Red', 'hex': '#FF0000'}, {'name': 'Blue', 'hex': '#0000FF'},
            {'name': 'Green', 'hex': '#00FF00'}, {'name': 'Yellow', 'hex': '#FFFF00'},
            {'name': 'Black', 'hex': '#000000'}, {'name': 'White', 'hex': '#FFFFFF'},
            {'name': 'Gray', 'hex': '#808080'}, {'name': 'Brown', 'hex': '#A52A2A'},
            {'name': 'Beige', 'hex': '#F5F5DC'}, {'name': 'Navy', 'hex': '#000080'},
            {'name': 'Maroon', 'hex': '#800000'}, {'name': 'Cream', 'hex': '#FFFDD0'},
            {'name': 'Charcoal', 'hex': '#36454F'}, {'name': 'Burgundy', 'hex': '#800020'},
            {'name': 'Tan', 'hex': '#D2B48C'}, {'name': 'Olive', 'hex': '#808000'},
            {'name': 'Teal', 'hex': '#008080'}, {'name': 'Magenta', 'hex': '#FF00FF'},
        ]
        colors = {}
        for color_data in colors_data:
            color, _ = Color.objects.get_or_create(
                name=color_data['name'],
                defaults={'hex_code': color_data['hex'], 'is_active': True}
            )
            colors[color_data['name']] = color
        
        # Create main category
        main_category, _ = Category.objects.get_or_create(
            name='Soft Furnishings',
            defaults={'description': 'Complete soft furnishings collection', 'is_active': True}
        )
        
        products_list = []
        products_per_category = count // len(categories_data)
        
        for cat_data in categories_data:
            sub_category, _ = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'parent': main_category,
                    'description': cat_data['description'],
                    'is_active': True
                }
            )
            
            product_templates = cat_data['products']
            price_min, price_max = cat_data['price_range']
            
            for i in range(products_per_category):
                template = product_templates[i % len(product_templates)]
                cost = Decimal(str(round(random.uniform(price_min * 0.4, price_max * 0.4), 2)))
                price = cost * Decimal(str(round(random.uniform(1.5, 2.5), 2)))
                
                sku = f"SF-{sub_category.name[:3].upper()}-{str(i+1).zfill(4)}"
                barcode = f"{random.randint(100000000000, 999999999999)}"
                while Product.objects.filter(barcode=barcode).exists():
                    barcode = f"{random.randint(100000000000, 999999999999)}"
                
                product = Product.objects.create(
                    name=template,
                    sku=sku,
                    barcode=barcode,
                    category=main_category,
                    subcategory=sub_category,
                    price=price,
                    cost=cost,
                    stock_quantity=random.randint(0, 200),
                    low_stock_threshold=random.randint(10, 50),
                    description=f"{template} - High quality soft furnishing item",
                    unit='piece',
                    is_taxable=True,
                    track_stock=True,
                    has_variants=cat_data['has_variants'],
                    is_active=True,
                )
                
                # Add variants
                if cat_data['has_variants']:
                    if cat_data['use_colors']:
                        selected_colors = random.sample(list(colors.values()), k=min(random.randint(3, 8), len(colors)))
                        product.available_colors.set(selected_colors)
                    
                    if cat_data['use_sizes']:
                        selected_sizes = random.sample(list(sizes.values()), k=min(random.randint(2, 5), len(sizes)))
                        product.available_sizes.set(selected_sizes)
                    
                    # Create variants
                    if cat_data['use_sizes'] and cat_data['use_colors']:
                        for size in product.available_sizes.all():
                            for color in product.available_colors.all():
                                ProductVariant.objects.create(
                                    product=product,
                                    size=size,
                                    color=color,
                                    price=price * Decimal(str(round(random.uniform(0.95, 1.15), 2))),
                                    cost=cost * Decimal(str(round(random.uniform(0.95, 1.10), 2))),
                                    stock_quantity=random.randint(0, 100),
                                    is_active=True
                                )
                    elif cat_data['use_colors']:
                        for color in product.available_colors.all():
                            ProductVariant.objects.create(
                                product=product,
                                color=color,
                                price=price * Decimal(str(round(random.uniform(0.95, 1.15), 2))),
                                cost=cost * Decimal(str(round(random.uniform(0.95, 1.10), 2))),
                                stock_quantity=random.randint(0, 100),
                                is_active=True
                            )
                    elif cat_data['use_sizes']:
                        for size in product.available_sizes.all():
                            ProductVariant.objects.create(
                                product=product,
                                size=size,
                                price=price * Decimal(str(round(random.uniform(0.95, 1.15), 2))),
                                cost=cost * Decimal(str(round(random.uniform(0.95, 1.10), 2))),
                                stock_quantity=random.randint(0, 100),
                                is_active=True
                            )
                
                products_list.append(product)
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(products_list)} products'))
        return products_list

    def create_customers(self, count, superuser, branch):
        """Create customers"""
        self.stdout.write(f'\n3. Creating {count} customers...')
        
        first_names = ['John', 'Jane', 'Mary', 'Peter', 'Sarah', 'David', 'Grace', 'James', 'Lucy', 'Michael']
        last_names = ['Mwangi', 'Ochieng', 'Kamau', 'Wanjiku', 'Onyango', 'Njoroge', 'Achieng', 'Kipchoge', 'Wanjala', 'Omondi']
        companies = ['Furniture Ltd', 'Interiors Co', 'Home Solutions', 'Design Studio', 'Comfort Homes']
        cities = ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret']
        
        customers = []
        for i in range(count):
            is_business = random.choice([True, False])
            if is_business:
                name = f"{random.choice(first_names)} {random.choice(companies)}"
                email = f"info@{name.lower().replace(' ', '')}.com"
            else:
                name = f"{random.choice(first_names)} {random.choice(last_names)}"
                email = f"{name.lower().replace(' ', '.')}@gmail.com"
            
            customer = Customer.objects.create(
                name=name,
                customer_type='business' if is_business else 'individual',
                email=email,
                phone=f"2547{random.randint(10000000, 99999999)}",
                address=f"Street {random.randint(1, 100)}, {random.choice(cities)}",
                city=random.choice(cities),
                country='Kenya',
                is_active=True,
                created_by=superuser,
                branch=branch if random.choice([True, False]) else None
            )
            customers.append(customer)
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(customers)} customers'))
        return customers

    def create_sales(self, count, products, customers, superuser, branch):
        """Create sales with different payment statuses"""
        self.stdout.write(f'\n4. Creating {count} sales with various payment statuses...')
        
        sales_created = []
        payment_statuses = ['fully_paid', 'partial', 'unpaid', 'installment_1_4', 'installment_3_4', 'installment_complete']
        
        for i in range(count):
            customer = random.choice(customers) if customers else None
            sale_type = random.choice(['pos', 'normal'])
            payment_status = random.choice(payment_statuses)
            
            # Create sale items
            num_items = random.randint(1, 5)
            sale_items = []
            subtotal = Decimal('0')
            
            for _ in range(num_items):
                product = random.choice(products)
                variant = None
                if product.has_variants and product.variants.exists():
                    variant = random.choice(list(product.variants.all()))
                    unit_price = variant.effective_price
                    stock = variant.stock_quantity
                else:
                    unit_price = product.price
                    stock = product.stock_quantity
                
                quantity = random.randint(1, min(5, stock // 2) if stock > 0 else 3)
                item_subtotal = Decimal(quantity) * unit_price
                subtotal += item_subtotal
                
                sale_items.append({
                    'product': product,
                    'variant': variant,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'subtotal': item_subtotal
                })
            
            tax_amount = subtotal * Decimal('0.16')  # 16% VAT
            discount_amount = Decimal('0') if random.random() > 0.2 else subtotal * Decimal(str(random.uniform(0.05, 0.15)))
            total = subtotal + tax_amount - discount_amount
            
            # Create sale
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
                notes=f"Sale {i+1} - {payment_status}"
            )
            
            # Create sale items and stock movements (stock is updated automatically by StockMovement.save())
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
                
                # Create stock movement (this automatically updates stock)
                StockMovement.objects.create(
                    branch=branch,
                    product=item_data['product'],
                    variant=item_data['variant'],
                    movement_type='sale',
                    quantity=item_data['quantity'],
                    unit_cost=unit_cost,
                    total_cost=item_data['quantity'] * unit_cost,
                    reference=sale.sale_number,
                    user=superuser,
                    notes=f'Sale {sale.sale_number}'
                )
            
            # Create invoice for normal sales
            invoice = None
            if sale_type == 'normal':
                invoice = Invoice.objects.create(
                    sale=sale,
                    branch=branch,
                    customer=customer,
                    customer_name=customer.name if customer else 'Walk-in Customer',
                    customer_email=customer.email if customer else '',
                    customer_phone=customer.phone if customer else '',
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
                else:
                    # Full payment for invoice
                    Payment.objects.create(
                        invoice=invoice,
                        amount=total,
                        payment_method=random.choice(['cash', 'mpesa', 'bank_transfer']),
                        payment_date=timezone.now().date() - timedelta(days=random.randint(0, 5)),
                        recorded_by=superuser,
                        notes='Full payment'
                    )
            
            elif payment_status == 'partial':
                if sale_type == 'normal' and invoice:
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
            
            elif payment_status == 'unpaid':
                # No payment - invoice remains unpaid
                pass
            
            elif payment_status.startswith('installment'):
                if sale_type == 'normal' and invoice:
                    # Create payment plan
                    num_installments = random.choice([4, 6, 8, 12])
                    installment_amount = total / Decimal(num_installments)
                    
                    payment_plan = PaymentPlan.objects.create(
                        invoice=invoice,
                        total_amount=total,
                        number_of_installments=num_installments,
                        installment_amount=installment_amount,
                        frequency=random.choice(['monthly', 'biweekly', 'weekly']),
                        start_date=timezone.now().date() - timedelta(days=random.randint(30, 180)),
                        created_by=superuser
                    )
                    
                    # Handle installment completion status
                    if payment_status == 'installment_1_4':
                        # 1/4 remaining - 75% paid
                        completed = int(num_installments * 0.75)
                        for i in range(completed):
                            payment_date = payment_plan.start_date + timedelta(days=i * 30)
                            Payment.objects.create(
                                invoice=invoice,
                                amount=installment_amount,
                                payment_method=random.choice(['cash', 'mpesa', 'bank_transfer']),
                                payment_date=payment_date,
                                recorded_by=superuser,
                                notes=f'Installment {i+1}/{num_installments}'
                            )
                        payment_plan.completed_installments = completed
                        payment_plan.last_payment_date = payment_plan.start_date + timedelta(days=completed * 30)
                        payment_plan.next_payment_date = payment_plan.last_payment_date + timedelta(days=30)
                        payment_plan.save()
                    
                    elif payment_status == 'installment_3_4':
                        # 3/4 remaining - 25% paid
                        completed = int(num_installments * 0.25)
                        for i in range(completed):
                            payment_date = payment_plan.start_date + timedelta(days=i * 30)
                            Payment.objects.create(
                                invoice=invoice,
                                amount=installment_amount,
                                payment_method=random.choice(['cash', 'mpesa', 'bank_transfer']),
                                payment_date=payment_date,
                                recorded_by=superuser,
                                notes=f'Installment {i+1}/{num_installments}'
                            )
                        payment_plan.completed_installments = completed
                        payment_plan.last_payment_date = payment_plan.start_date + timedelta(days=completed * 30)
                        payment_plan.next_payment_date = payment_plan.last_payment_date + timedelta(days=30)
                        payment_plan.save()
                    
                    elif payment_status == 'installment_complete':
                        # All installments paid
                        for i in range(num_installments):
                            payment_date = payment_plan.start_date + timedelta(days=i * 30)
                            Payment.objects.create(
                                invoice=invoice,
                                amount=installment_amount,
                                payment_method=random.choice(['cash', 'mpesa', 'bank_transfer']),
                                payment_date=payment_date,
                                recorded_by=superuser,
                                notes=f'Installment {i+1}/{num_installments}'
                            )
                        payment_plan.completed_installments = num_installments
                        payment_plan.last_payment_date = payment_plan.start_date + timedelta(days=(num_installments - 1) * 30)
                        payment_plan.is_active = False
                        payment_plan.save()
            
            sales_created.append(sale)
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(sales_created)} sales'))

    def create_expenses(self, count, superuser, branch):
        """Create expenses relevant to soft furnishings business"""
        self.stdout.write(f'\n5. Creating {count} expenses...')
        
        # Expense categories for soft furnishings business
        categories_data = [
            {'name': 'Fabric Purchase', 'description': 'Purchase of fabrics and upholstery materials'},
            {'name': 'Foam & Cushioning', 'description': 'Purchase of foam and cushioning materials'},
            {'name': 'Hardware & Tools', 'description': 'Purchase of hardware, tools, and equipment'},
            {'name': 'Rent & Utilities', 'description': 'Shop rent, electricity, water bills'},
            {'name': 'Transportation', 'description': 'Delivery and transportation costs'},
            {'name': 'Marketing & Advertising', 'description': 'Marketing and advertising expenses'},
            {'name': 'Staff Salaries', 'description': 'Employee salaries and wages'},
            {'name': 'Insurance', 'description': 'Business insurance premiums'},
            {'name': 'Maintenance & Repairs', 'description': 'Equipment maintenance and repairs'},
            {'name': 'Office Supplies', 'description': 'Office supplies and stationery'},
            {'name': 'Professional Services', 'description': 'Legal, accounting, consulting fees'},
            {'name': 'Telecommunications', 'description': 'Phone, internet, and communication costs'},
        ]
        
        categories = []
        for cat_data in categories_data:
            category, _ = ExpenseCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={'description': cat_data['description'], 'is_active': True}
            )
            categories.append(category)
        
        # Expense amounts by category
        expense_ranges = {
            'Fabric Purchase': (5000, 100000),
            'Foam & Cushioning': (3000, 50000),
            'Hardware & Tools': (1000, 30000),
            'Rent & Utilities': (20000, 150000),
            'Transportation': (500, 10000),
            'Marketing & Advertising': (2000, 50000),
            'Staff Salaries': (15000, 200000),
            'Insurance': (5000, 50000),
            'Maintenance & Repairs': (1000, 25000),
            'Office Supplies': (500, 10000),
            'Professional Services': (5000, 100000),
            'Telecommunications': (1000, 15000),
        }
        
        vendors = [
            'Fabric Suppliers Ltd', 'Foam World', 'Hardware Express', 'Utility Company',
            'Transport Services', 'Marketing Agency', 'Insurance Co', 'Repair Services',
            'Office Depot', 'Law Firm', 'Telecom Provider'
        ]
        
        for i in range(count):
            category = random.choice(categories)
            amount_range = expense_ranges.get(category.name, (1000, 50000))
            amount = Decimal(str(round(random.uniform(amount_range[0], amount_range[1]), 2)))
            
            Expense.objects.create(
                branch=branch,
                category=category,
                amount=amount,
                description=f"{category.name} expense - {random.choice(['Monthly', 'Weekly', 'One-time', 'Quarterly'])} payment",
                payment_method=random.choice(['cash', 'mpesa', 'bank', 'card']),
                status=random.choice(['approved', 'paid']),
                vendor=random.choice(vendors),
                receipt_number=f"RCP-{random.randint(100000, 999999)}",
                expense_date=timezone.now().date() - timedelta(days=random.randint(0, 90)),
                created_by=superuser,
                approved_by=superuser if random.choice([True, False]) else None,
                notes=f"Expense for {category.name.lower()}"
            )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {count} expenses'))
