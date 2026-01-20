from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, EmailValidator
from products.models import Product, ProductVariant
from decimal import Decimal
import uuid


class Customer(models.Model):
    """Customer model for managing customer information"""
    CUSTOMER_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
    ]
    
    name = models.CharField(max_length=200, db_index=True)
    customer_code = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    branch = models.ForeignKey(
        'settings.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers',
        help_text='Primary branch for this customer (optional - customers can be shared)'
    )
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='individual')
    email = models.EmailField(blank=True, validators=[EmailValidator()])
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    tax_id = models.CharField(max_length=50, blank=True, help_text='Tax ID or VAT number')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    wallet_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Customer wallet balance (credit available for future purchases)'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='customers_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.customer_code:
            # Generate unique customer code
            prefix = 'CUST'
            last_customer = Customer.objects.order_by('-id').first()
            if last_customer and last_customer.customer_code:
                try:
                    last_num = int(last_customer.customer_code.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            self.customer_code = f"{prefix}-{str(new_num).zfill(6)}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.customer_code})"
    
    @property
    def total_invoices(self):
        """Get total number of invoices for this customer"""
        return self.invoices.count()
    
    @property
    def total_outstanding(self):
        """Get total outstanding balance"""
        from django.db.models import Sum
        return self.invoices.aggregate(
            total=Sum('balance')
        )['total'] or 0


class Sale(models.Model):
    """Sales transactions"""
    SALE_TYPES = [
        ('pos', 'POS Sale'),
        ('normal', 'Normal Sale'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-PESA'),
        ('other', 'Other'),
    ]

    sale_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    sale_type = models.CharField(
        max_length=20, 
        choices=SALE_TYPES, 
        default='pos',
        help_text='POS Sale: immediate payment, no invoice. Normal Sale: creates invoice, supports partial payments.'
    )
    branch = models.ForeignKey(
        'settings.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales',
        help_text='Branch where sale was made'
    )
    cashier = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='sales'
    )
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    tax_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    change = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    delivery_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Delivery method (pickup, delivery, etc.)'
    )
    delivery_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Additional cost for delivery'
    )
    shipping_address = models.TextField(
        blank=True,
        null=True,
        help_text='Shipping address for delivery'
    )
    shipping_location = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text='Shipping location/area'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['sale_number']),
            models.Index(fields=['cashier', 'created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.sale_number:
            self.sale_number = f"SALE-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sale_number} - {self.total} KES"

    @property
    def item_count(self):
        """Get total number of items in sale"""
        from django.db.models import Sum
        return self.items.aggregate(total=Sum('quantity'))['total'] or 0


class SaleItem(models.Model):
    """Items in a sale"""
    sale = models.ForeignKey(
        Sale, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE,
        related_name='sale_items'
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_items',
        help_text='Product variant (size/color) if applicable'
    )
    size = models.ForeignKey(
        'products.Size',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Size (stored for historical records)'
    )
    color = models.ForeignKey(
        'products.Color',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Color (stored for historical records)'
    )
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        variant_info = ""
        if self.variant:
            variant_parts = []
            if self.variant.size:
                variant_parts.append(f"Size: {self.variant.size.name}")
            if self.variant.color:
                variant_parts.append(f"Color: {self.variant.color.name}")
            if variant_parts:
                variant_info = f" ({', '.join(variant_parts)})"
        return f"{self.product.name}{variant_info} x {self.quantity} = {self.subtotal} KES"

    def save(self, *args, **kwargs):
        # Auto-calculate subtotal
        self.subtotal = self.quantity * self.unit_price
        
        # Store size and color from variant if variant is set
        if self.variant:
            self.size = self.variant.size
            self.color = self.variant.color
        
        super().save(*args, **kwargs)


class Invoice(models.Model):
    """Invoices for sales with payment tracking"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    branch = models.ForeignKey(
        'settings.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoices',
        help_text='Branch where invoice was created'
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='invoices',
        null=True,
        blank=True,
        help_text='Original sale if invoice was generated from a sale'
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        help_text='Customer for this invoice'
    )
    # Keep these fields for backward compatibility and quick reference
    customer_name = models.CharField(max_length=200, blank=True, help_text='Customer name (auto-filled from customer)')
    customer_email = models.EmailField(blank=True, help_text='Customer email (auto-filled from customer)')
    customer_phone = models.CharField(max_length=20, blank=True, help_text='Customer phone (auto-filled from customer)')
    customer_address = models.TextField(blank=True, help_text='Customer address (auto-filled from customer)')
    
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Total amount paid so far'
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Remaining balance'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    due_date = models.DateField(null=True, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invoices_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
        
        # Auto-fill customer details from customer object if customer is set
        if self.customer:
            if not self.customer_name:
                self.customer_name = self.customer.name
            if not self.customer_email:
                self.customer_email = self.customer.email
            if not self.customer_phone:
                self.customer_phone = self.customer.phone
            if not self.customer_address:
                self.customer_address = self.customer.address
        
        # Calculate balance
        self.balance = self.total - self.amount_paid
        
        # Update status based on payment
        if self.amount_paid == 0:
            if self.status not in ['draft', 'cancelled']:
                self.status = 'sent'
        elif self.amount_paid >= self.total:
            self.status = 'paid'
            self.balance = Decimal('0')
        elif self.amount_paid > 0:
            self.status = 'partial'
        
        # Check if overdue
        if self.due_date and self.balance > 0:
            from django.utils import timezone
            if timezone.now().date() > self.due_date:
                if self.status not in ['paid', 'cancelled']:
                    self.status = 'overdue'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.invoice_number} - {self.total} KES ({self.status})"
    
    @property
    def payment_percentage(self):
        """Get payment percentage"""
        if self.total == 0:
            return 0
        return (self.amount_paid / self.total) * 100
    
    @property
    def is_fully_paid(self):
        """Check if invoice is fully paid"""
        return self.amount_paid >= self.total
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        if not self.due_date or self.is_fully_paid:
            return False
        from django.utils import timezone
        return timezone.now().date() > self.due_date


class InvoiceItem(models.Model):
    """Items in an invoice"""
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='invoice_items'
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_items'
    )
    size = models.ForeignKey(
        'products.Size',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    color = models.ForeignKey(
        'products.Color',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def save(self, *args, **kwargs):
        # Auto-calculate subtotal
        self.subtotal = self.quantity * self.unit_price
        
        # Store size and color from variant if variant is set
        if self.variant:
            self.size = self.variant.size
            self.color = self.variant.color
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        variant_info = ""
        if self.variant:
            variant_parts = []
            if self.variant.size:
                variant_parts.append(f"Size: {self.variant.size.name}")
            if self.variant.color:
                variant_parts.append(f"Color: {self.variant.color.name}")
            if variant_parts:
                variant_info = f" ({', '.join(variant_parts)})"
        return f"{self.product.name}{variant_info} x {self.quantity} = {self.subtotal} KES"


class Payment(models.Model):
    """Payments made against invoices"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-PESA'),
        ('bank_transfer', 'Bank Transfer'),
        ('other', 'Other'),
    ]
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    payment_date = models.DateField()
    reference = models.CharField(max_length=100, blank=True, help_text='Payment reference number')
    notes = models.TextField(blank=True)
    
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payments_recorded'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['invoice', 'payment_date']),
            models.Index(fields=['payment_date']),
        ]
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update invoice amount_paid
        invoice = self.invoice
        invoice.amount_paid = invoice.payments.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        invoice.save()
        
        # Note: Journal entries for payments are created in PaymentViewSet.create()
        # Initial payments from sales are handled by the sale journal entry
        # This ensures we don't double-count payments
    
    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        # Recalculate invoice amount_paid
        invoice.amount_paid = invoice.payments.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        invoice.save()
    
    def __str__(self):
        return f"Payment of {self.amount} KES for {self.invoice.invoice_number} on {self.payment_date}"


class PaymentPlan(models.Model):
    """Payment plans for invoices with installments"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('custom', 'Custom'),
    ]
    
    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payment_plan',
        help_text='Invoice this payment plan is for'
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Total amount to be paid in installments'
    )
    number_of_installments = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text='Total number of installments'
    )
    installment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Amount per installment'
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='monthly',
        help_text='Payment frequency'
    )
    start_date = models.DateField(help_text='Date of first payment')
    next_payment_date = models.DateField(
        null=True,
        blank=True,
        help_text='Next payment due date'
    )
    last_payment_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date of last payment'
    )
    completed_installments = models.IntegerField(
        default=0,
        help_text='Number of installments completed'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this payment plan is active'
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payment_plans_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice']),
            models.Index(fields=['next_payment_date']),
            models.Index(fields=['is_active']),
        ]
    
    def save(self, *args, **kwargs):
        # Calculate next payment date if not set
        if not self.next_payment_date and self.is_active:
            from django.utils import timezone
            from datetime import timedelta
            
            if self.completed_installments == 0:
                self.next_payment_date = self.start_date
            else:
                # Calculate next payment based on frequency
                last_payment = self.start_date
                if self.last_payment_date:
                    last_payment = self.last_payment_date
                
                if self.frequency == 'daily':
                    self.next_payment_date = last_payment + timedelta(days=1)
                elif self.frequency == 'weekly':
                    self.next_payment_date = last_payment + timedelta(weeks=1)
                elif self.frequency == 'biweekly':
                    self.next_payment_date = last_payment + timedelta(weeks=2)
                elif self.frequency == 'monthly':
                    # Add approximately 30 days
                    self.next_payment_date = last_payment + timedelta(days=30)
                elif self.frequency == 'quarterly':
                    self.next_payment_date = last_payment + timedelta(days=90)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Payment Plan for {self.invoice.invoice_number} - {self.completed_installments}/{self.number_of_installments} installments"
    
    @property
    def remaining_installments(self):
        """Get remaining number of installments"""
        return self.number_of_installments - self.completed_installments
    
    @property
    def is_complete(self):
        """Check if payment plan is complete"""
        return self.completed_installments >= self.number_of_installments or self.invoice.is_fully_paid


class PaymentReminder(models.Model):
    """Reminders for upcoming or overdue payments"""
    REMINDER_TYPES = [
        ('upcoming', 'Upcoming Payment'),
        ('overdue', 'Overdue Payment'),
        ('custom', 'Custom Reminder'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('dismissed', 'Dismissed'),
    ]
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='reminders',
        help_text='Invoice this reminder is for'
    )
    payment_plan = models.ForeignKey(
        PaymentPlan,
        on_delete=models.CASCADE,
        related_name='reminders',
        null=True,
        blank=True,
        help_text='Payment plan if reminder is for installment'
    )
    reminder_type = models.CharField(
        max_length=20,
        choices=REMINDER_TYPES,
        default='upcoming'
    )
    reminder_date = models.DateField(help_text='Date when reminder should be sent')
    due_date = models.DateField(help_text='Payment due date')
    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Amount due on this date'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    message = models.TextField(blank=True, help_text='Custom reminder message')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reminders_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['reminder_date', '-created_at']
        indexes = [
            models.Index(fields=['invoice', 'reminder_date']),
            models.Index(fields=['status']),
            models.Index(fields=['reminder_date']),
        ]
    
    def __str__(self):
        return f"Reminder for {self.invoice.invoice_number} - {self.reminder_type} on {self.reminder_date}"
    
    @property
    def is_overdue(self):
        """Check if reminder is for overdue payment"""
        from django.utils import timezone
        return timezone.now().date() > self.due_date
    
    @property
    def days_until_due(self):
        """Get days until payment is due"""
        from django.utils import timezone
        delta = self.due_date - timezone.now().date()
        return delta.days


class CustomerWalletTransaction(models.Model):
    """Track customer wallet transactions (credits and debits)"""
    TRANSACTION_TYPES = [
        ('credit', 'Credit (Added to Wallet)'),
        ('debit', 'Debit (Used from Wallet)'),
    ]
    
    SOURCE_TYPES = [
        ('overpayment', 'Overpayment from Sale'),
        ('refund', 'Refund'),
        ('manual', 'Manual Adjustment'),
        ('payment', 'Payment from Wallet'),
        ('other', 'Other'),
    ]
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='wallet_transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, default='other')
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Wallet balance after this transaction'
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
        help_text='Sale that triggered this transaction (if applicable)'
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
        help_text='Invoice related to this transaction (if applicable)'
    )
    reference = models.CharField(max_length=100, blank=True, help_text='Reference number or code')
    notes = models.TextField(blank=True, help_text='Transaction notes')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='wallet_transactions_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['sale']),
            models.Index(fields=['invoice']),
        ]
    
    def __str__(self):
        return f"{self.customer.name} - {self.get_transaction_type_display()} {self.amount} KES ({self.get_source_type_display()})"
