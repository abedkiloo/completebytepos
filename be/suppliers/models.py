from django.db import models
from django.contrib.auth.models import User
from django.core.validators import EmailValidator, MinValueValidator
from decimal import Decimal


class Supplier(models.Model):
    """Supplier model for managing supplier information"""
    SUPPLIER_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('manufacturer', 'Manufacturer'),
        ('distributor', 'Distributor'),
        ('wholesaler', 'Wholesaler'),
    ]
    
    PAYMENT_TERMS_CHOICES = [
        ('net_15', 'Net 15'),
        ('net_30', 'Net 30'),
        ('net_45', 'Net 45'),
        ('net_60', 'Net 60'),
        ('cod', 'Cash on Delivery'),
        ('prepaid', 'Prepaid'),
        ('custom', 'Custom Terms'),
    ]
    
    name = models.CharField(max_length=200, db_index=True, help_text='Supplier name or company name')
    supplier_code = models.CharField(max_length=50, unique=True, editable=False, db_index=True, help_text='Unique supplier code')
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPE_CHOICES, default='business')
    
    # Contact Information
    contact_person = models.CharField(max_length=200, blank=True, help_text='Primary contact person name')
    email = models.EmailField(blank=True, validators=[EmailValidator()], db_index=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    alternate_phone = models.CharField(max_length=20, blank=True, help_text='Alternate phone number')
    
    # Address Information
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True, help_text='State or Province')
    country = models.CharField(max_length=100, default='Kenya')
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Business Information
    tax_id = models.CharField(max_length=50, blank=True, help_text='Tax ID or VAT number')
    registration_number = models.CharField(max_length=100, blank=True, help_text='Business registration number')
    website = models.URLField(blank=True, help_text='Company website')
    
    # Financial Information
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='net_30', help_text='Default payment terms')
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Credit limit (0 means no credit limit)'
    )
    account_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Current account balance (amount owed to supplier)'
    )
    
    # Additional Information
    notes = models.TextField(blank=True, help_text='Additional notes about the supplier')
    rating = models.IntegerField(
        default=5,
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text='Supplier rating (1-5)'
    )
    is_preferred = models.BooleanField(default=False, help_text='Mark as preferred supplier')
    is_active = models.BooleanField(default=True, help_text='Whether this supplier is active')
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suppliers_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['supplier_code']),
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['is_active']),
            models.Index(fields=['supplier_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.supplier_code})"
    
    def save(self, *args, **kwargs):
        if not self.supplier_code:
            # Generate unique supplier code
            import uuid
            self.supplier_code = f"SUP-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    @property
    def full_address(self):
        """Get full formatted address"""
        parts = [self.address, self.city, self.state, self.country, self.postal_code]
        return ', '.join(filter(None, parts))
    
    @property
    def primary_contact(self):
        """Get primary contact information"""
        if self.contact_person:
            return f"{self.contact_person} - {self.phone or self.email}"
        return self.phone or self.email or 'No contact info'
    
    @property
    def is_credit_available(self):
        """Check if credit is available"""
        if self.credit_limit == 0:
            return False
        return self.account_balance < self.credit_limit
