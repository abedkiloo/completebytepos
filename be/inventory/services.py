"""
Inventory service layer - handles all inventory/stock movement business logic
"""
import uuid
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, F, QuerySet
from django.core.exceptions import ValidationError
from .models import StockMovement
from products.models import Product, ProductVariant
from settings.models import Branch
from settings.utils import get_current_branch, is_branch_support_enabled
from services.base import BaseService


class StockMovementService(BaseService):
    """Service for stock movement operations"""
    
    def __init__(self):
        super().__init__(StockMovement)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None, request=None) -> QuerySet:
        """
        Build queryset with filters for stock movement listing.
        Moves query building logic from views to service layer.
        
        Args:
            filters: Dictionary with filter parameters:
                - branch_id: int (branch ID)
                - show_all: bool or str ('true'/'false')
                - product: int (product ID)
                - movement_type: str
                - date_from: str (date string)
                - date_to: str (date string)
            request: HttpRequest (optional, for branch detection)
        
        Returns:
            QuerySet of stock movements with proper select_related
        """
        queryset = self.model.objects.all().select_related('product', 'user', 'branch')
        
        if not filters:
            filters = {}
        
        # Handle branch filtering
        if is_branch_support_enabled():
            show_all = filters.get('show_all', 'false')
            if isinstance(show_all, str):
                show_all = show_all.lower() == 'true'
            
            if not show_all:
                branch_id = filters.get('branch_id')
                if not branch_id and request:
                    current_branch = get_current_branch(request)
                    if current_branch:
                        branch_id = current_branch.id
                
                if branch_id:
                    try:
                        queryset = queryset.filter(branch_id=int(branch_id))
                    except (ValueError, TypeError):
                        queryset = queryset.none()
        
        # Product filter
        product_id = filters.get('product')
        if product_id:
            try:
                queryset = queryset.filter(product_id=int(product_id))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        # Movement type filter
        movement_type = filters.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        
        # Date filters
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    @transaction.atomic
    def adjust_stock(self, product_id: int, variant_id: Optional[int],
                    quantity: int, notes: str = '', user=None,
                    branch: Optional[Branch] = None, unit_cost: Optional[Decimal] = None) -> StockMovement:
        """
        Adjust stock for a product or variant.
        Creates stock movement and updates product/variant stock quantity.
        """
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise ValidationError('Product not found')
        
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                raise ValidationError('Variant not found for this product')
        
        # Update stock quantity
        if variant:
            variant.stock_quantity += quantity
            if variant.stock_quantity < 0:
                raise ValidationError(f'Insufficient stock. Available: {variant.stock_quantity - quantity}')
            variant.save()
            stock_quantity_after = variant.stock_quantity
        else:
            if not product.track_stock:
                raise ValidationError('Product does not track stock')
            product.stock_quantity += quantity
            if product.stock_quantity < 0:
                raise ValidationError(f'Insufficient stock. Available: {product.stock_quantity - quantity}')
            product.save()
            stock_quantity_after = product.stock_quantity
        
        # Calculate costs
        if unit_cost is None:
            unit_cost = variant.cost if variant and variant.cost else product.cost
        
        total_cost = unit_cost * abs(quantity) if unit_cost else None
        
        # Create stock movement
        movement = StockMovement.objects.create(
            branch=branch,
            product=product,
            variant=variant,
            movement_type='adjustment',
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reference=f'ADJ-{product.sku}',
            notes=notes or f'Stock adjustment: {quantity:+d}',
            user=user
        )
        
        return movement
    
    @transaction.atomic
    def purchase_stock(self, product_id: int, variant_id: Optional[int],
                      quantity: int, unit_cost: Decimal, notes: str = '',
                      user=None, branch: Optional[Branch] = None,
                      reference: str = '') -> StockMovement:
        """
        Record a stock purchase (add stock).
        Creates stock movement and updates product/variant stock quantity.
        """
        if quantity <= 0:
            raise ValidationError('Purchase quantity must be positive')
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise ValidationError('Product not found')
        
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                raise ValidationError('Variant not found for this product')
        
        # Update stock quantity
        if variant:
            variant.stock_quantity += quantity
            variant.cost = unit_cost  # Update variant cost
            variant.save()
        else:
            if not product.track_stock:
                raise ValidationError('Product does not track stock')
            product.stock_quantity += quantity
            product.cost = unit_cost  # Update product cost
            product.save()
        
        total_cost = unit_cost * quantity
        
        # Create stock movement
        movement = StockMovement.objects.create(
            branch=branch,
            product=product,
            variant=variant,
            movement_type='purchase',
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reference=reference or f'PUR-{product.sku}',
            notes=notes or f'Stock purchase: {quantity} units',
            user=user
        )
        
        return movement
    
    @transaction.atomic
    def transfer_stock(self, product_id: int, variant_id: Optional[int],
                      quantity: int, from_branch: Branch, to_branch: Branch,
                      notes: str = '', user=None) -> List[StockMovement]:
        """
        Transfer stock between branches.
        Creates two movements: one for source (negative) and one for destination (positive).
        """
        if quantity <= 0:
            raise ValidationError('Transfer quantity must be positive')
        
        if from_branch == to_branch:
            raise ValidationError('Source and destination branches must be different')
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise ValidationError('Product not found')
        
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                raise ValidationError('Variant not found for this product')
        
        # Check available stock at source branch
        if variant:
            stock_quantity = variant.stock_quantity
        else:
            if not product.track_stock:
                raise ValidationError('Product does not track stock')
            stock_quantity = product.stock_quantity
        
        if stock_quantity < quantity:
            raise ValidationError(f'Insufficient stock. Available: {stock_quantity}')
        
        # Get unit cost
        unit_cost = variant.cost if variant and variant.cost else product.cost
        total_cost = unit_cost * quantity if unit_cost else None
        
        # Generate unique transfer ID to pair the two movements
        # This allows undo logic to find paired movements even with custom notes
        transfer_id = uuid.uuid4().hex[:8].upper()
        shared_reference = f'TRF-{transfer_id}'
        
        # Create outbound movement (from source)
        outbound = StockMovement.objects.create(
            branch=from_branch,
            product=product,
            variant=variant,
            movement_type='transfer',
            quantity=-quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reference=f'{shared_reference}-OUT',
            notes=notes or f'Transfer out to {to_branch.name}',
            user=user
        )
        
        # Create inbound movement (to destination)
        inbound = StockMovement.objects.create(
            branch=to_branch,
            product=product,
            variant=variant,
            movement_type='transfer',
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reference=f'{shared_reference}-IN',
            notes=notes or f'Transfer in from {from_branch.name}',
            user=user
        )
        
        # Note: Stock quantities are updated automatically by the StockMovement.save() method
        # The outbound movement (negative quantity) reduces stock, and inbound (positive) increases it
        # Net effect is 0 for global stock, but both movements are recorded for branch tracking
        
        return [outbound, inbound]
    
    def get_inventory_report(self, branch: Optional[Branch] = None,
                            product_id: Optional[int] = None) -> Dict[str, Any]:
        """Get inventory report with stock levels and movements"""
        queryset = self.model.objects.all()
        
        if branch:
            queryset = queryset.filter(branch=branch)
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Aggregate by movement type
        by_type = list(queryset.values('movement_type').annotate(
            total_quantity=Sum('quantity'),
            count=Count('id')
        ))
        
        # Recent movements
        recent_movements = queryset.order_by('-created_at')[:20]
        
        return {
            'by_movement_type': by_type,
            'recent_movements': [
                {
                    'id': m.id,
                    'product': m.product.name,
                    'movement_type': m.movement_type,
                    'quantity': m.quantity,
                    'created_at': m.created_at
                }
                for m in recent_movements
            ]
        }
