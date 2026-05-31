from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F

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

    # Fields whose updates must NOT re-apply a stock side-effect.
    # When `model.save(update_fields=...)` is called with a subset of these,
    # we treat the save as pure metadata and skip stock mutation.
    METADATA_ONLY_FIELDS = frozenset({'notes', 'reference'})

    def save(self, *args, **kwargs):
        # Calculate total cost if unit_cost is provided
        if self.unit_cost and not self.total_cost:
            self.total_cost = abs(self.quantity) * self.unit_cost

        # If the caller is updating only metadata fields (e.g. marking a movement
        # as undone), persist the row but do NOT re-run the stock side-effect.
        # This contract is relied on by InventoryViewSet.undo and similar flows.
        update_fields = kwargs.get('update_fields')
        skip_stock_update = bool(
            update_fields
            and set(update_fields).issubset(self.METADATA_ONLY_FIELDS)
        )

        super().save(*args, **kwargs)

        if skip_stock_update:
            return

        self._apply_stock_effect()

    def _stock_delta(self) -> int:
        """
        Signed change this movement applies to the target stock_quantity.
        Positive = adds stock, negative = removes stock.
        """
        mt = self.movement_type
        if mt in ('sale', 'damage', 'waste', 'expired'):
            return -abs(self.quantity)
        if mt in ('purchase', 'return'):
            return abs(self.quantity)
        if mt in ('adjustment', 'transfer'):
            # Caller-controlled sign: positive adds, negative removes.
            return int(self.quantity)
        # Unknown movement types default to a stock-removing effect to be safe.
        return -abs(self.quantity)

    def _allow_negative_stock_for_sale(self) -> bool:
        """When sales stock validation is off, sale movements may drive qty below zero."""
        if self.movement_type != 'sale':
            return False
        from sales.module_settings import sales_validate_stock_before_sale

        return not sales_validate_stock_before_sale()

    def _apply_stock_effect(self):
        """
        Atomically apply this movement's effect to the target Product or
        ProductVariant row.

        Uses ``select_for_update()`` so concurrent sales of the same SKU
        serialise on that row (real row-level locks on PostgreSQL; a no-op on
        SQLite, which already serialises writes at the DB level).

        Raises ``ValidationError`` if the result would leave stock negative
        — the caller's surrounding ``@transaction.atomic`` rolls back, so the
        ledger row that was just inserted is undone along with any other work
        done in the same transaction (e.g. the parent Sale).

        This is the single source of truth for stock_quantity mutations.
        No other code path should write to Product.stock_quantity or
        ProductVariant.stock_quantity directly.
        """
        delta = self._stock_delta()
        if delta == 0:
            return

        # Run the locked read + checked write in a savepoint so a negative-stock
        # ValidationError rolls back cleanly inside an outer atomic block.
        with transaction.atomic():
            if self.variant_id:
                if not self.variant.product.track_stock:
                    return
                locked = ProductVariant.objects.select_for_update().get(pk=self.variant_id)
                if not self._allow_negative_stock_for_sale():
                    self._guard_negative(locked.stock_quantity, delta, str(locked))
                update_kwargs = {'stock_quantity': F('stock_quantity') + delta}
                if self.movement_type == 'purchase' and self.unit_cost and delta > 0:
                    update_kwargs['cost'] = self._weighted_average_cost(
                        old_qty=locked.stock_quantity,
                        old_cost=locked.cost if locked.cost is not None else locked.product.cost,
                        added_qty=delta,
                        added_unit_cost=self.unit_cost,
                    )
                ProductVariant.objects.filter(pk=self.variant_id).update(**update_kwargs)
            else:
                if not self.product.track_stock:
                    return
                locked = Product.objects.select_for_update().get(pk=self.product_id)
                if not self._allow_negative_stock_for_sale():
                    self._guard_negative(locked.stock_quantity, delta, locked.name)
                update_kwargs = {'stock_quantity': F('stock_quantity') + delta}
                if self.movement_type == 'purchase' and self.unit_cost and delta > 0:
                    update_kwargs['cost'] = self._weighted_average_cost(
                        old_qty=locked.stock_quantity,
                        old_cost=locked.cost,
                        added_qty=delta,
                        added_unit_cost=self.unit_cost,
                    )
                Product.objects.filter(pk=self.product_id).update(**update_kwargs)

    @staticmethod
    def _guard_negative(current_qty: int, delta: int, target_label: str) -> None:
        """Raise if applying ``delta`` to ``current_qty`` would go below zero."""
        if current_qty + delta < 0:
            raise ValidationError(
                f"Insufficient stock for {target_label}. "
                f"Available: {current_qty}, requested change: {delta}."
            )

    @staticmethod
    def _weighted_average_cost(*, old_qty, old_cost, added_qty, added_unit_cost):
        """Compute a weighted-average cost basis after adding stock at a new unit cost."""
        old_cost = Decimal(str(old_cost or 0))
        unit_cost = Decimal(str(added_unit_cost))
        old_qty = Decimal(str(old_qty))
        added_qty = Decimal(str(added_qty))
        total_qty = old_qty + added_qty
        if total_qty == 0:
            return unit_cost
        return ((old_qty * old_cost) + (added_qty * unit_cost)) / total_qty
