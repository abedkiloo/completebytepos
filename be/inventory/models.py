from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from products.models import Product, ProductVariant


class StockMovement(models.Model):
    """Inventory movements (add/remove stock)"""
    MOVEMENT_TYPES = [
        ('sale', 'Sale'),
        ('purchase', 'Purchase'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
        ('damage', 'Damage'),
        ('transfer', 'Transfer'),
        ('waste', 'Waste'),
        ('expired', 'Expired'),
    ]

    branch = models.ForeignKey(
        'settings.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text='Branch where stock movement occurred'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text='Product variant if applicable'
    )
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()  # Positive for add, negative for remove
    unit_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text='Cost per unit for this movement'
    )
    total_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text='Total cost for this movement'
    )
    reference = models.CharField(max_length=100, blank=True)  # Sale number, PO number, etc.
    notes = models.TextField(blank=True)
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='stock_movements'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['movement_type', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        sign = '+' if self.quantity > 0 else ''
        return f"{self.product.name} - {self.movement_type} - {sign}{self.quantity}"

    def save(self, *args, **kwargs):
        # Calculate total cost if unit_cost is provided
        if self.unit_cost and not self.total_cost:
            self.total_cost = abs(self.quantity) * self.unit_cost
        
        # Check if we're only updating specific fields (e.g., notes, reference) to avoid stock recalculation
        update_fields = kwargs.get('update_fields')
        # Skip stock update if only updating non-stock-affecting fields
        # Safely access first element - update_fields can be frozenset, tuple, list, etc.
        skip_stock_update = False
        if update_fields and len(update_fields) == 1:
            # Convert to list to safely access first element (handles frozenset, tuple, etc.)
            fields_list = list(update_fields)
            if fields_list and fields_list[0] in ['notes', 'reference']:
                skip_stock_update = True
        
        super().save(*args, **kwargs)
        
        # Skip stock update if we're only updating notes or reference (e.g., when marking as undone or updating reference)
        if skip_stock_update:
            return
        
        # Update stock - variant stock if variant exists, otherwise product stock
        if self.variant:
            # Update variant stock
            if not self.variant.product.track_stock:
                return
            
            if self.movement_type == 'sale':
                self.variant.stock_quantity = max(0, self.variant.stock_quantity - abs(self.quantity))
            elif self.movement_type in ['purchase', 'return']:
                self.variant.stock_quantity += abs(self.quantity)
            elif self.movement_type == 'adjustment':
                self.variant.stock_quantity = max(0, self.variant.stock_quantity + self.quantity)
            elif self.movement_type == 'transfer':
                # For transfers, use the quantity directly (positive adds, negative subtracts)
                self.variant.stock_quantity = max(0, self.variant.stock_quantity + self.quantity)
            else:
                self.variant.stock_quantity = max(0, self.variant.stock_quantity - abs(self.quantity))
            
            # Update variant cost if this is a purchase with unit_cost
            if self.movement_type == 'purchase' and self.unit_cost:
                if self.variant.stock_quantity > 0:
                    old_value = (self.variant.stock_quantity - abs(self.quantity)) * (self.variant.cost or self.variant.product.cost)
                    new_value = abs(self.quantity) * self.unit_cost
                    new_cost = (old_value + new_value) / self.variant.stock_quantity
                    self.variant.cost = new_cost
            
            self.variant.save()
        else:
            # Update product stock (existing logic)
            if not self.product.track_stock:
                return
            
            if self.movement_type == 'sale':
                self.product.stock_quantity = max(0, self.product.stock_quantity - abs(self.quantity))
            elif self.movement_type in ['purchase', 'return']:
                self.product.stock_quantity += abs(self.quantity)
            elif self.movement_type == 'adjustment':
                self.product.stock_quantity = max(0, self.product.stock_quantity + self.quantity)
            elif self.movement_type == 'transfer':
                # For transfers, use the quantity directly (positive adds, negative subtracts)
                self.product.stock_quantity = max(0, self.product.stock_quantity + self.quantity)
            else:
                self.product.stock_quantity = max(0, self.product.stock_quantity - abs(self.quantity))
            
            # Update product cost if this is a purchase with unit_cost
            if self.movement_type == 'purchase' and self.unit_cost:
                if self.product.stock_quantity > 0:
                    old_value = (self.product.stock_quantity - abs(self.quantity)) * self.product.cost
                    new_value = abs(self.quantity) * self.unit_cost
                    self.product.cost = (old_value + new_value) / self.product.stock_quantity
            
            self.product.save()
