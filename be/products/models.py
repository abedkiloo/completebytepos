from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, Q


def _non_negative_stock_constraint(name: str):
    """Django 4.x uses check=; Django 5.1+ uses condition=."""
    q = Q(stock_quantity__gte=0)
    try:
        return CheckConstraint(condition=q, name=name)
    except TypeError:
        return CheckConstraint(check=q, name=name)


class Size(models.Model):
    """Product sizes (e.g., S, M, L, XL, etc.)"""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text='Short code (e.g., S, M, L)')
    display_order = models.IntegerField(default=0, help_text='Order for display')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class Color(models.Model):
    """Product colors"""
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=7, blank=True, help_text='Hex color code (e.g., #FF0000)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Category(models.Model):
    """Product categories"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name
    
    @property
    def product_count(self):
        """Get number of products in this category"""
        return self.products.filter(is_active=True).count()


class UnitOfMeasure(models.Model):
    """Extensible units of measure for products (piece, kg, roll, etc.)."""

    code = models.CharField(max_length=20, unique=True, db_index=True)
    label = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'label']
        verbose_name = 'Unit of measure'
        verbose_name_plural = 'Units of measure'

    def __str__(self):
        return self.label


class Product(models.Model):
    """Products in the system"""

    # Legacy defaults — new units are added via UnitOfMeasure rows.
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('l', 'Liter'),
        ('ml', 'Milliliter'),
        ('box', 'Box'),
        ('pack', 'Pack'),
        ('bottle', 'Bottle'),
        ('can', 'Can'),
        ('roll', 'Roll'),
    ]

    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True, db_index=True)
    barcode = models.CharField(max_length=50, blank=True, null=True, db_index=True, unique=True)
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products',
        help_text='Main category'
    )
    subcategory = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategory_products',
        help_text='Subcategory (must be a child of the main category)'
    )
    # Variant support
    has_variants = models.BooleanField(
        default=False,
        help_text='Does this product have size/color variants?'
    )
    available_sizes = models.ManyToManyField(
        Size,
        blank=True,
        related_name='products',
        help_text='Available sizes for this product'
    )
    available_colors = models.ManyToManyField(
        Color,
        blank=True,
        related_name='products',
        help_text='Available colors for this product'
    )
    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Maximum retail price (MRP) — list/sticker price for display',
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Selling price — used for POS, sales, invoices, and reports',
    )
    cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Cost price'
    )
    stock_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.IntegerField(default=10, validators=[MinValueValidator(0)])
    reorder_quantity = models.IntegerField(default=50, validators=[MinValueValidator(0)], help_text='Quantity to order when restocking')
    unit = models.CharField(
        max_length=20,
        default='piece',
        help_text='Unit code — must match an active UnitOfMeasure.code',
    )
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    description = models.TextField(blank=True)
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        help_text='Supplier for this product'
    )
    supplier_name = models.CharField(max_length=200, blank=True, help_text='Legacy supplier name (deprecated - use supplier FK)')
    supplier_contact = models.CharField(max_length=100, blank=True, help_text='Legacy supplier contact (deprecated - use supplier FK)')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)], help_text='Tax rate percentage')
    is_taxable = models.BooleanField(default=True)
    track_stock = models.BooleanField(default=True, help_text='Track inventory for this product')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
            models.Index(fields=['category', 'is_active']),
        ]
        constraints = [
            # Backstop against overselling: defence-in-depth alongside the
            # row-locked check in StockMovement._apply_stock_effect(). Even if
            # something writes stock directly in the future, the DB refuses to
            # store a negative quantity.
            _non_negative_stock_constraint('product_stock_quantity_non_negative'),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_low_stock(self):
        """Check if product is low on stock"""
        if not self.track_stock:
            return False
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def selling_price(self):
        """Selling price used for transactions (same as ``price`` column)."""
        return self.price

    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.price > 0:
            return ((self.price - self.cost) / self.price) * 100
        return 0
    
    @property
    def profit_amount(self):
        """Calculate profit amount"""
        return self.price - self.cost
    
    @property
    def total_value(self):
        """Calculate total inventory value"""
        return self.stock_quantity * self.cost
    
    @property
    def needs_reorder(self):
        """Check if product needs to be reordered"""
        if not self.track_stock:
            return False
        return self.stock_quantity <= self.low_stock_threshold
    
    def save(self, *args, **kwargs):
        # Auto-generate SKU if not provided
        if not self.sku:
            import uuid
            self.sku = f"SKU-{uuid.uuid4().hex[:8].upper()}"
        
        # Auto-populate category from subcategory's parent if subcategory is set but category doesn't match
        if self.subcategory:
            if self.subcategory.parent:
                # If category is not set or doesn't match subcategory's parent, auto-set it
                if not self.category or self.category != self.subcategory.parent:
                    self.category = self.subcategory.parent
        
        # Validate subcategory is a child of category (final check)
        if self.subcategory and self.category:
            if self.subcategory.parent != self.category:
                raise ValueError("Subcategory must be a child of the main category")
        
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    """Product variants (size + color combinations)"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    size = models.ForeignKey(
        Size,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    sku = models.CharField(max_length=50, unique=True, db_index=True, help_text='Variant-specific SKU')
    barcode = models.CharField(max_length=50, blank=True, null=True, db_index=True, unique=True)
    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Variant MRP (overrides product MRP when set)',
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Variant selling price (overrides product selling price when set)',
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Variant-specific cost (overrides product cost if set)'
    )
    stock_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        help_text='Variant-specific low stock threshold'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['product', 'size', 'color']]
        ordering = ['product', 'size', 'color']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['product', 'is_active']),
        ]
        constraints = [
            _non_negative_stock_constraint('productvariant_stock_quantity_non_negative'),
        ]

    def __str__(self):
        variant_parts = []
        if self.size:
            variant_parts.append(f"Size: {self.size.name}")
        if self.color:
            variant_parts.append(f"Color: {self.color.name}")
        variant_str = " - ".join(variant_parts) if variant_parts else "Default"
        return f"{self.product.name} ({variant_str})"

    @property
    def effective_price(self):
        """Selling price used at POS and on sale lines."""
        return self.price if self.price is not None else self.product.price

    @property
    def effective_mrp(self):
        """List/MRP for display (variant override, else product)."""
        if self.mrp is not None:
            return self.mrp
        return self.product.mrp if self.product.mrp else self.effective_price

    @property
    def selling_price(self):
        """Alias for effective selling price."""
        return self.effective_price

    @property
    def effective_cost(self):
        """Get effective cost (variant cost or product cost)"""
        return self.cost if self.cost is not None else self.product.cost

    @property
    def is_low_stock(self):
        """Check if variant is low on stock"""
        threshold = self.low_stock_threshold if self.low_stock_threshold is not None else self.product.low_stock_threshold
        return self.stock_quantity <= threshold

    def save(self, *args, **kwargs):
        # Auto-generate SKU if not provided
        if not self.sku:
            import uuid
            base_sku = self.product.sku
            variant_parts = []
            if self.size:
                variant_parts.append(self.size.code)
            if self.color:
                variant_parts.append(self.color.name[:3].upper())
            variant_suffix = "-".join(variant_parts) if variant_parts else uuid.uuid4().hex[:4].upper()
            self.sku = f"{base_sku}-{variant_suffix}"
        super().save(*args, **kwargs)
