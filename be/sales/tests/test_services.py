"""
Comprehensive unit tests for Sales Services
Tests all business logic, edge cases, and error handling
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from sales.models import Sale, SaleItem, Invoice, InvoiceItem, Payment, Customer, PaymentPlan, CustomerWalletTransaction
from products.models import Product, Category, ProductVariant, Size, Color
from sales.services import (
    SaleService, InvoiceService, PaymentService, CustomerService
)
from settings.models import Tenant, Branch
from django.contrib.auth.models import User
from django.utils import timezone


class CustomerServiceTestCase(TestCase):
    """Tests for CustomerService"""
    
    def setUp(self):
        self.service = CustomerService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
        )
        self.branch = Branch.objects.create(
            name='Test Branch', code='BR1', tenant=self.tenant, created_by=self.user
        )
    
    def test_search_customers_by_name(self):
        """Test searching customers by name"""
        Customer.objects.create(
            name='John Doe',
            email='john@test.com',
            phone='1234567890',
            is_active=True
        )
        Customer.objects.create(
            name='Jane Smith',
            email='jane@test.com',
            phone='0987654321',
            is_active=True
        )
        
        results = self.service.search_customers('John')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, 'John Doe')
    
    def test_search_customers_by_email(self):
        """Test searching customers by email"""
        Customer.objects.create(
            name='John Doe',
            email='john@test.com',
            phone='1234567890',
            is_active=True
        )
        
        results = self.service.search_customers('john@test.com')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].email, 'john@test.com')
    
    def test_search_customers_empty_query(self):
        """Test search with empty query returns empty list"""
        Customer.objects.create(name='John Doe', is_active=True)
        
        results = self.service.search_customers('')
        self.assertEqual(len(results), 0)
    
    def test_update_wallet_balance_credit(self):
        """Test adding credit to customer wallet"""
        customer = Customer.objects.create(
            name='John Doe',
            wallet_balance=Decimal('100.00'),
            is_active=True
        )
        
        transaction = self.service.update_wallet_balance(
            customer,
            Decimal('50.00'),
            'credit',
            'manual',
            reference='TEST-001',
            notes='Test credit',
            user=self.user
        )
        
        customer.refresh_from_db()
        self.assertEqual(customer.wallet_balance, Decimal('150.00'))
        self.assertEqual(transaction.transaction_type, 'credit')
        self.assertEqual(transaction.balance_after, Decimal('150.00'))
    
    def test_update_wallet_balance_debit(self):
        """Test deducting from customer wallet"""
        customer = Customer.objects.create(
            name='John Doe',
            wallet_balance=Decimal('100.00'),
            is_active=True
        )
        
        transaction = self.service.update_wallet_balance(
            customer,
            Decimal('30.00'),
            'debit',
            'payment',
            reference='TEST-001',
            notes='Test debit',
            user=self.user
        )
        
        customer.refresh_from_db()
        self.assertEqual(customer.wallet_balance, Decimal('70.00'))
        self.assertEqual(transaction.transaction_type, 'debit')
    
    def test_update_wallet_balance_insufficient_funds(self):
        """Test that debit fails with insufficient wallet balance"""
        customer = Customer.objects.create(
            name='John Doe',
            wallet_balance=Decimal('50.00'),
            is_active=True
        )
        
        with self.assertRaises(ValidationError):
            self.service.update_wallet_balance(
                customer,
                Decimal('100.00'),
                'debit',
                'payment',
                user=self.user
            )
    
    def test_get_customer_statistics(self):
        """Test getting customer statistics"""
        customer = Customer.objects.create(
            name='John Doe',
            wallet_balance=Decimal('100.00'),
            is_active=True
        )
        
        stats = self.service.get_customer_statistics(customer.id)
        
        self.assertIn('total_invoices', stats)
        self.assertIn('total_outstanding', stats)
        self.assertIn('wallet_balance', stats)
        self.assertEqual(stats['wallet_balance'], 100.0)
    
    def test_get_customer_statistics_nonexistent(self):
        """Test getting statistics for nonexistent customer"""
        with self.assertRaises(ValidationError):
            self.service.get_customer_statistics(99999)


class SaleServiceTestCase(TestCase):
    """Tests for SaleService"""
    
    def setUp(self):
        self.service = SaleService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
        )
        self.branch = Branch.objects.create(
            name='Test Branch', code='BR1', tenant=self.tenant, created_by=self.user
        )
        self.category = Category.objects.create(name='Test Category', is_active=True)
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=100,
            track_stock=True,
            is_active=True
        )
        self.customer = Customer.objects.create(
            name='Test Customer',
            wallet_balance=Decimal('200.00'),
            is_active=True
        )
    
    def test_validate_sale_items_success(self):
        """Test successful validation of sale items"""
        items_data = [
            {
                'product_id': self.product.id,
                'quantity': 2,
                'unit_price': Decimal('100.00')
            }
        ]
        
        validated = self.service.validate_sale_items(items_data)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]['quantity'], 2)
        self.assertEqual(validated[0]['subtotal'], Decimal('200.00'))
    
    def test_validate_sale_items_missing_product(self):
        """Test validation fails with missing product"""
        items_data = [
            {
                'product_id': 99999,
                'quantity': 1
            }
        ]
        
        with self.assertRaises(ValidationError):
            self.service.validate_sale_items(items_data)
    
    def test_validate_sale_items_insufficient_stock(self):
        """Test validation fails with insufficient stock"""
        items_data = [
            {
                'product_id': self.product.id,
                'quantity': 200  # More than available (100)
            }
        ]
        
        with self.assertRaises(ValidationError):
            self.service.validate_sale_items(items_data)
    
    def test_validate_sale_items_with_variant(self):
        """Test validation with product variant"""
        size = Size.objects.create(name='Small', code='S', is_active=True)
        color = Color.objects.create(name='Red', is_active=True)
        self.product.has_variants = True
        self.product.save()
        self.product.available_sizes.add(size)
        self.product.available_colors.add(color)
        
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='TEST-001-S-RED',
            price=Decimal('110.00'),
            cost=Decimal('55.00'),
            stock_quantity=50,
            is_active=True
        )
        
        items_data = [
            {
                'product_id': self.product.id,
                'variant_id': variant.id,
                'quantity': 2
            }
        ]
        
        validated = self.service.validate_sale_items(items_data)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]['variant'], variant)
        self.assertEqual(validated[0]['unit_price'], Decimal('110.00'))
    
    def test_create_sale_success(self):
        """Test successful sale creation"""
        items_data = [
            {
                'product_id': self.product.id,
                'quantity': 2,
                'unit_price': Decimal('100.00')
            }
        ]
        
        sale_data = {
            'sale_type': 'pos',
            'payment_method': 'cash',
            'amount_paid': Decimal('200.00'),
            'tax_amount': Decimal('0'),
            'discount_amount': Decimal('0'),
            'delivery_cost': Decimal('0')
        }
        
        sale = self.service.create_sale(
            sale_data,
            items_data,
            self.user,
            self.branch
        )
        
        self.assertIsNotNone(sale.id)
        self.assertEqual(sale.total, Decimal('200.00'))
        self.assertEqual(sale.items.count(), 1)
        
        # Check stock was updated
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 98)
    
    def test_create_sale_calculates_totals(self):
        """Test that sale totals are calculated correctly"""
        items_data = [
            {
                'product_id': self.product.id,
                'quantity': 2,
                'unit_price': Decimal('100.00')
            }
        ]
        
        sale_data = {
            'sale_type': 'pos',
            'payment_method': 'cash',
            'amount_paid': Decimal('250.00'),
            'tax_amount': Decimal('20.00'),
            'discount_amount': Decimal('10.00'),
            'delivery_cost': Decimal('5.00')
        }
        
        sale = self.service.create_sale(
            sale_data,
            items_data,
            self.user,
            self.branch
        )
        
        # Subtotal: 200, Tax: 20, Discount: -10, Delivery: 5 = 215
        self.assertEqual(sale.subtotal, Decimal('200.00'))
        self.assertEqual(sale.total, Decimal('215.00'))
        self.assertEqual(sale.change, Decimal('35.00'))  # 250 - 215
    
    def test_handle_wallet_transactions_debit(self):
        """Test wallet debit transaction"""
        sale = Sale.objects.create(
            sale_type='pos',
            branch=self.branch,
            cashier=self.user,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            payment_method='cash',
            amount_paid=Decimal('50.00'),
            change=Decimal('0')
        )
        
        result = self.service.handle_wallet_transactions(
            self.customer,
            Decimal('100.00'),
            Decimal('50.00'),
            use_wallet=True,
            wallet_amount_requested=Decimal('50.00'),
            sale=sale,
            user=self.user
        )
        
        self.customer.refresh_from_db()
        self.assertEqual(result['wallet_amount_used'], Decimal('50.00'))
        self.assertEqual(self.customer.wallet_balance, Decimal('150.00'))
    
    def test_handle_wallet_transactions_overpayment(self):
        """Test wallet credit from overpayment"""
        sale = Sale.objects.create(
            sale_type='pos',
            branch=self.branch,
            cashier=self.user,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            payment_method='cash',
            amount_paid=Decimal('150.00'),
            change=Decimal('0')
        )
        
        result = self.service.handle_wallet_transactions(
            self.customer,
            Decimal('100.00'),
            Decimal('150.00'),
            use_wallet=False,
            wallet_amount_requested=Decimal('0'),
            sale=sale,
            user=self.user
        )
        
        self.customer.refresh_from_db()
        self.assertEqual(result['wallet_credit_added'], Decimal('50.00'))
        self.assertEqual(self.customer.wallet_balance, Decimal('250.00'))
    
    def test_get_sale_statistics(self):
        """Test getting sale statistics"""
        Sale.objects.create(
            sale_type='pos',
            branch=self.branch,
            cashier=self.user,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            discount_amount=Decimal('5.00'),
            total=Decimal('105.00'),
            payment_method='cash',
            amount_paid=Decimal('105.00'),
            change=Decimal('0')
        )
        
        stats = self.service.get_sale_statistics()
        
        self.assertIn('total_sales', stats)
        self.assertIn('pos_sales', stats)
        self.assertIn('total_revenue', stats)
        self.assertEqual(stats['total_sales'], 1)
        self.assertEqual(stats['pos_sales'], 1)


class InvoiceServiceTestCase(TestCase):
    """Tests for InvoiceService"""
    
    def setUp(self):
        self.service = InvoiceService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
        )
        self.branch = Branch.objects.create(
            name='Test Branch', code='BR1', tenant=self.tenant, created_by=self.user
        )
        self.category = Category.objects.create(name='Test Category', is_active=True)
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        self.customer = Customer.objects.create(
            name='Test Customer',
            email='test@example.com',
            phone='1234567890',
            is_active=True
        )
        self.sale = Sale.objects.create(
            sale_type='normal',
            branch=self.branch,
            cashier=self.user,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            discount_amount=Decimal('5.00'),
            total=Decimal('105.00'),
            payment_method='cash',
            amount_paid=Decimal('50.00'),
            change=Decimal('0')
        )
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('100.00')
        )
    
    def test_create_invoice_from_sale_success(self):
        """Test successful invoice creation from sale"""
        invoice = self.service.create_invoice_from_sale(
            self.sale,
            customer=self.customer,
            user=self.user,
            amount_paid=Decimal('50.00')
        )
        
        self.assertIsNotNone(invoice.id)
        self.assertEqual(invoice.sale, self.sale)
        self.assertEqual(invoice.customer, self.customer)
        self.assertEqual(invoice.total, Decimal('105.00'))
        self.assertEqual(invoice.balance, Decimal('55.00'))
        self.assertEqual(invoice.status, 'sent')
        self.assertEqual(invoice.items.count(), 1)
    
    def test_create_invoice_from_sale_with_payment(self):
        """Test invoice creation with full payment"""
        invoice = self.service.create_invoice_from_sale(
            self.sale,
            customer=self.customer,
            user=self.user,
            amount_paid=Decimal('105.00')
        )
        
        self.assertEqual(invoice.status, 'paid')
        self.assertEqual(invoice.balance, Decimal('0'))
        self.assertEqual(invoice.payments.count(), 1)
    
    def test_create_payment_plan_success(self):
        """Test successful payment plan creation"""
        invoice = self.service.create_invoice_from_sale(
            self.sale,
            customer=self.customer,
            user=self.user,
            amount_paid=Decimal('0')
        )
        
        payment_plan = self.service.create_payment_plan(
            invoice,
            number_of_installments=3,
            frequency='monthly',
            start_date='2024-01-01',
            user=self.user
        )
        
        self.assertIsNotNone(payment_plan.id)
        self.assertEqual(payment_plan.number_of_installments, 3)
        self.assertEqual(payment_plan.frequency, 'monthly')
        self.assertEqual(payment_plan.installment_amount, invoice.balance / 3)
    
    def test_create_payment_plan_fully_paid_invoice(self):
        """Test payment plan creation fails for fully paid invoice"""
        invoice = self.service.create_invoice_from_sale(
            self.sale,
            customer=self.customer,
            user=self.user,
            amount_paid=Decimal('105.00')
        )
        
        with self.assertRaises(ValidationError):
            self.service.create_payment_plan(
                invoice,
                number_of_installments=3,
                frequency='monthly',
                start_date='2024-01-01',
                user=self.user
            )


class PaymentServiceTestCase(TestCase):
    """Tests for PaymentService"""
    
    def setUp(self):
        self.service = PaymentService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
        )
        self.branch = Branch.objects.create(
            name='Test Branch', code='BR1', tenant=self.tenant, created_by=self.user
        )
        self.customer = Customer.objects.create(
            name='Test Customer',
            is_active=True
        )
        self.sale = Sale.objects.create(
            sale_type='normal',
            branch=self.branch,
            cashier=self.user,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            payment_method='cash',
            amount_paid=Decimal('0'),
            change=Decimal('0')
        )
        self.invoice = Invoice.objects.create(
            sale=self.sale,
            branch=self.branch,
            customer=self.customer,
            customer_name=self.customer.name,
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            amount_paid=Decimal('0'),
            balance=Decimal('100.00'),
            status='sent',
            issued_date=timezone.now().date(),
            created_by=self.user
        )
    
    def test_create_payment_success(self):
        """Test successful payment creation"""
        payment = self.service.create_payment(
            self.invoice,
            amount=Decimal('50.00'),
            payment_method='cash',
            user=self.user,
            notes='Partial payment'
        )
        
        self.assertIsNotNone(payment.id)
        self.assertEqual(payment.amount, Decimal('50.00'))
        
        # Check invoice was updated
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal('50.00'))
        self.assertEqual(self.invoice.balance, Decimal('50.00'))
        self.assertEqual(self.invoice.status, 'partial')
    
    def test_create_payment_exceeds_balance(self):
        """Test payment creation fails when amount exceeds balance"""
        with self.assertRaises(ValidationError):
            self.service.create_payment(
                self.invoice,
                amount=Decimal('150.00'),
                payment_method='cash',
                user=self.user
            )
    
    def test_create_payment_full_payment(self):
        """Test full payment updates invoice status to paid"""
        payment = self.service.create_payment(
            self.invoice,
            amount=Decimal('100.00'),
            payment_method='cash',
            user=self.user
        )
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'paid')
        self.assertEqual(self.invoice.balance, Decimal('0'))