"""
Inventory stock movements and on-hand quantity.

Public entry points:
    - ``StockMovementService.adjust_stock`` / ``purchase_stock`` /
      ``transfer_stock`` / ``undo_transfer`` / ``build_queryset``
    - Called from ``StockMovementViewSet`` under ``/api/inventory/``

Side effects:
    Updates ``Product`` / ``ProductVariant.stock_quantity`` on movement create,
    optional FIFO layers, and ``AuditLog`` rows (``stock_*`` with before/after).

Does not create sales or wallet postings — those live in ``sales``.
"""
import re
import uuid
from datetime import timedelta
from django.utils import timezone
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, F, QuerySet
from django.core.exceptions import ValidationError
from .models import StockMovement
from products.models import Product, ProductVariant
from settings.models import Branch
from settings.utils import get_current_branch, is_branch_support_enabled
from services.base import BaseService
from services.datetime_filters import inclusive_end_datetime, inclusive_start_datetime


def catalog_unit_cost(product: Product, variant: Optional[ProductVariant] = None) -> Decimal:
    """
    Return the effective catalog unit cost for a product or variant.

    Args:
        product: Parent product (used when variant has no cost).
        variant: Optional variant; its ``cost`` wins when not None.

    Returns:
        Non-negative ``Decimal`` cost. Missing/null costs become ``0``.

    Bounds:
        No upper bound beyond the Decimal stored on the model field.
    """
    if variant is not None and variant.cost is not None:
        return Decimal(str(variant.cost))
    return Decimal(str(product.cost or 0))


def resolve_intake_unit_cost(
    *,
    product: Product,
    variant: Optional[ProductVariant] = None,
    unit_cost=None,
    use_catalog_cost: bool = False,
) -> Decimal:
    """
    Resolve unit cost for stock intake (purchase or positive adjust).

    Args:
        product: Product being received.
        variant: Optional variant receiving stock.
        unit_cost: Explicit batch cost. When provided must be ``> 0``.
        use_catalog_cost: If True, reuse positive catalog cost and ignore
            a missing ``unit_cost``.

    Returns:
        Positive ``Decimal`` unit cost for the intake layer/movement.

    Raises:
        ValidationError: Catalog cost is zero when reuse requested, or
            ``unit_cost`` is missing/≤0 when a new batch cost is required.

    Bounds:
        Resolved cost must be ``> 0``. There is no configured upper limit.
    """
    catalog = catalog_unit_cost(product, variant)
    if use_catalog_cost:
        if catalog <= 0:
            raise ValidationError(
                'Current cost is zero. Enter a new unit cost for this stock batch.'
            )
        return catalog

    if unit_cost is not None and unit_cost != '':
        resolved = Decimal(str(unit_cost))
        if resolved <= 0:
            raise ValidationError('Unit cost must be greater than zero.')
        return resolved

    # Backward-compatible: omitted unit_cost falls back to positive catalog cost.
    if catalog > 0:
        return catalog

    raise ValidationError(
        'Unit cost is required because catalog cost is zero. '
        'Enter the cost for this batch, or update the product cost first.'
    )


def _on_hand(product: Product, variant: Optional[ProductVariant] = None) -> int:
    if variant is not None:
        return int(variant.stock_quantity or 0)
    return int(product.stock_quantity or 0)


class StockMovementService(BaseService):
    """
    Business operations for inventory ledger rows and on-hand quantity.

    Owns create paths for adjust / purchase / transfer / undo. Views stay thin
    and call these methods. Every mutating path emits an ``AuditLog`` entry
    with ``stock_before`` / ``stock_after`` when known.

    Attributes:
        model: Bound to ``StockMovement``.
    """
    
    def __init__(self):
        super().__init__(StockMovement)

    def _audit_movement(
        self,
        movement: StockMovement,
        *,
        event: str,
        request=None,
        stock_before=None,
        stock_after=None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Append one inventory ``AuditLog`` row for a movement.

        Args:
            movement: Persisted movement (must have ``id``).
            event: Audit action verb (e.g. ``stock_adjust``, ``stock_purchase``).
            request: Optional HTTP request for actor IP/path; may be None.
            stock_before: On-hand units before the movement; int or None.
            stock_after: On-hand units after the movement; int or None.
            extra: Optional extra JSON fields merged into ``changes``.

        Returns:
            None. Failures inside ``log_audit`` are swallowed by design.
        """
        from utils.audit_events import log_stock_movement_event

        payload = {
            'product_id': movement.product_id,
            'variant_id': movement.variant_id,
            'movement_id': movement.id,
            'reference': movement.reference or '',
            'notes': movement.notes or '',
        }
        if stock_before is not None:
            payload['stock_before'] = stock_before
        if stock_after is not None:
            payload['stock_after'] = stock_after
        if extra:
            payload.update(extra)
        log_stock_movement_event(request, movement, event=event, payload=payload)
    
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
        queryset = self.model.objects.all().select_related(
            'product', 'user', 'branch', 'variant', 'variant__size', 'variant__color'
        )
        
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
            queryset = queryset.filter(created_at__gte=inclusive_start_datetime(date_from))
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=inclusive_end_datetime(date_to))
        
        return queryset.order_by('-created_at')
    
    @transaction.atomic
    def adjust_stock(self, product_id: int, variant_id: Optional[int],
                    quantity: int, notes: str = '', user=None,
                    branch: Optional[Branch] = None, unit_cost: Optional[Decimal] = None,
                    use_catalog_cost: bool = False, request=None) -> StockMovement:
        """
        Apply a signed stock adjustment and write an audit row.

        Creates one ``StockMovement`` (type ``adjustment``). Positive
        ``quantity`` adds stock; negative removes stock. Audits
        ``stock_before`` / ``stock_after``.

        Args:
            product_id: PK of the product (must exist).
            variant_id: Optional variant PK on that product; None = product level.
            quantity: Signed units to apply. Must be non-zero. No hard upper
                bound beyond the movement integer field; negative adjusts cannot
                drive on-hand below 0 (ValidationError).
            notes: Free-text note stored on the movement (may be empty).
            user: Acting user stored on the movement; may be None for jobs.
            branch: Optional branch for multi-branch installs.
            unit_cost: Required path for +qty when catalog cost is zero.
            use_catalog_cost: If True, reuse positive catalog cost for +qty.
            request: Optional HTTP request for audit IP/path.

        Returns:
            The created ``StockMovement`` (stock already applied).

        Raises:
            ValidationError: Product/variant missing, product does not track
                stock, ``quantity == 0``, cost rules fail, or resulting stock
                would be negative.
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
        
        # Track-stock guard: adjustments only make sense for tracked stock.
        if not variant and not product.track_stock:
            raise ValidationError('Product does not track stock')

        if quantity == 0:
            raise ValidationError('Adjustment quantity must be non-zero')

        from inventory.stock_layers import (
            apply_fifo_sale_drain,
            create_layer_for_purchase,
            ensure_opening_layer_if_needed,
            layers_enabled,
        )

        # Positive intake: resolve new-vs-catalog cost. Negative: stamp movement
        # with catalog/FIFO cost for write-off valuation (layer drain below).
        if quantity > 0:
            unit_cost = resolve_intake_unit_cost(
                product=product,
                variant=variant,
                unit_cost=unit_cost,
                use_catalog_cost=use_catalog_cost,
            )
            if layers_enabled():
                ensure_opening_layer_if_needed(
                    product_id=product.id,
                    variant_id=variant.id if variant else None,
                )
        else:
            if unit_cost is None or unit_cost == '':
                unit_cost = catalog_unit_cost(product, variant)
            else:
                unit_cost = Decimal(str(unit_cost))

        total_cost = unit_cost * abs(quantity) if unit_cost else None

        stock_before = _on_hand(product, variant)

        # Create stock movement. StockMovement.save() applies the +/-quantity
        # delta atomically with row locking and raises ValidationError if the
        # result would go below zero, rolling back this @transaction.atomic.
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

        if layers_enabled():
            if quantity > 0:
                if variant is not None and variant.price is not None:
                    sell = variant.price
                else:
                    sell = product.price
                create_layer_for_purchase(
                    movement=movement,
                    unit_sell_price=Decimal(str(sell or 0)),
                )
            else:
                apply_fifo_sale_drain(
                    product_id=product.id,
                    variant_id=variant.id if variant else None,
                    quantity=abs(quantity),
                )

        if variant is not None:
            variant.refresh_from_db(fields=['stock_quantity'])
        else:
            product.refresh_from_db(fields=['stock_quantity'])
        self._audit_movement(
            movement,
            event='stock_adjust',
            request=request,
            stock_before=stock_before,
            stock_after=_on_hand(product, variant),
        )
        return movement
    
    @transaction.atomic
    def purchase_stock(self, product_id: int, variant_id: Optional[int],
                      quantity: int, unit_cost: Decimal = None, notes: str = '',
                      user=None, branch: Optional[Branch] = None,
                      reference: str = '',
                      unit_sell_price: Optional[Decimal] = None,
                      use_catalog_cost: bool = False, request=None) -> StockMovement:
        """
        Record a stock purchase (add stock).

        When stock layers are enabled, creates a FIFO layer with this intake's
        cost + selling price and syncs catalog price/cost from the oldest open
        layer (WAC blending is skipped). Cost may be a new batch cost or the
        existing catalog cost (``use_catalog_cost``).
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
        
        # Track-stock guard.
        if not variant and not product.track_stock:
            raise ValidationError('Product does not track stock')

        unit_cost = resolve_intake_unit_cost(
            product=product,
            variant=variant,
            unit_cost=unit_cost,
            use_catalog_cost=use_catalog_cost,
        )
        total_cost = unit_cost * quantity

        from inventory.stock_layers import (
            create_layer_for_purchase,
            ensure_opening_layer_if_needed,
            layers_enabled,
        )

        # Capture any pre-layer on-hand as an opening layer before the purchase
        # movement increases quantity (so FIFO drains old stock first).
        if layers_enabled():
            ensure_opening_layer_if_needed(
                product_id=product.id,
                variant_id=variant.id if variant else None,
            )

        stock_before = _on_hand(product, variant)

        # Create stock movement. StockMovement.save() atomically increments
        # stock_quantity. With layers enabled, catalog cost is set from the
        # oldest open layer after the layer is created (not WAC-blended).
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

        if layers_enabled():
            if unit_sell_price is None or unit_sell_price == '':
                if variant is not None and variant.price is not None:
                    unit_sell_price = variant.price
                else:
                    unit_sell_price = product.price
            create_layer_for_purchase(
                movement=movement,
                unit_sell_price=Decimal(str(unit_sell_price or 0)),
            )

        if variant is not None:
            variant.refresh_from_db(fields=['stock_quantity'])
        else:
            product.refresh_from_db(fields=['stock_quantity'])
        self._audit_movement(
            movement,
            event='stock_purchase',
            request=request,
            stock_before=stock_before,
            stock_after=_on_hand(product, variant),
        )
        return movement
    
    @transaction.atomic
    def transfer_stock(self, product_id: int, variant_id: Optional[int],
                      quantity: int, from_branch: Branch, to_branch: Branch,
                      notes: str = '', user=None, request=None) -> List[StockMovement]:
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
        stock_before = _on_hand(product, variant)
        
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
        if variant is not None:
            variant.refresh_from_db(fields=['stock_quantity'])
        else:
            product.refresh_from_db(fields=['stock_quantity'])
        stock_after = _on_hand(product, variant)
        self._audit_movement(
            outbound,
            event='stock_transfer',
            request=request,
            stock_before=stock_before,
            stock_after=stock_after,
            extra={'paired_movement_id': inbound.id, 'direction': 'out'},
        )
        self._audit_movement(
            inbound,
            event='stock_transfer',
            request=request,
            stock_before=stock_before,
            stock_after=stock_after,
            extra={'paired_movement_id': outbound.id, 'direction': 'in'},
        )
        
        return [outbound, inbound]

    def find_paired_transfer_movement(self, movement: StockMovement) -> Optional[StockMovement]:
        """Locate the inbound/outbound pair for a transfer movement."""
        paired = None
        if movement.reference and movement.reference.startswith('TRF-'):
            ref_match = re.match(r'^(TRF-[A-Z0-9]+)-OUT$', movement.reference)
            if ref_match:
                transfer_id = ref_match.group(1)
                paired = StockMovement.objects.filter(
                    reference=f'{transfer_id}-IN',
                    movement_type='transfer',
                    product=movement.product,
                    variant=movement.variant,
                ).exclude(id=movement.id).first()
            else:
                ref_match = re.match(r'^(TRF-[A-Z0-9]+)-IN$', movement.reference)
                if ref_match:
                    transfer_id = ref_match.group(1)
                    paired = StockMovement.objects.filter(
                        reference=f'{transfer_id}-OUT',
                        movement_type='transfer',
                        product=movement.product,
                        variant=movement.variant,
                    ).exclude(id=movement.id).first()

        if not paired and movement.quantity < 0:
            filter_kwargs = {
                'product': movement.product,
                'variant': movement.variant,
                'movement_type': 'transfer',
                'quantity': -movement.quantity,
                'created_at__gte': movement.created_at - timedelta(seconds=5),
                'created_at__lte': movement.created_at + timedelta(seconds=5),
            }
            if movement.branch and movement.branch.name:
                filter_kwargs['notes__icontains'] = movement.branch.name
            paired = StockMovement.objects.filter(**filter_kwargs).exclude(id=movement.id).first()

        if not paired and movement.quantity > 0 and movement.notes:
            match = re.search(r'Transfer in from (.+)$', movement.notes, re.IGNORECASE)
            if match:
                source_branch_name = match.group(1).strip()
                paired = StockMovement.objects.filter(
                    product=movement.product,
                    variant=movement.variant,
                    movement_type='transfer',
                    quantity=-movement.quantity,
                    created_at__gte=movement.created_at - timedelta(seconds=5),
                    created_at__lte=movement.created_at + timedelta(seconds=5),
                    branch__name__icontains=source_branch_name,
                    notes__icontains='Transfer out',
                ).exclude(id=movement.id).first()

        if not paired and movement.quantity > 0:
            paired = StockMovement.objects.filter(
                product=movement.product,
                variant=movement.variant,
                movement_type='transfer',
                quantity=-movement.quantity,
                created_at__gte=movement.created_at - timedelta(seconds=5),
                created_at__lte=movement.created_at + timedelta(seconds=5),
                notes__icontains='Transfer out',
            ).exclude(id=movement.id).first()

        return paired

    @transaction.atomic
    def undo_transfer(
        self, movement: StockMovement, user=None, request=None
    ) -> Tuple[StockMovement, Optional[StockMovement], Optional[StockMovement]]:
        """
        Reverse a transfer movement (and its pair if present).

        Returns (original_movement, reverse_movement, reverse_paired_or_none).
        Raises ValidationError on business rule violations.
        """
        if movement.movement_type != 'transfer':
            raise ValidationError('Can only undo transfer movements')
        if movement.notes and 'UNDONE' in movement.notes:
            raise ValidationError('This transfer has already been undone')

        paired_movement = self.find_paired_transfer_movement(movement)
        reverse_quantity = -movement.quantity

        if movement.variant:
            stock_quantity = movement.variant.stock_quantity
        else:
            stock_quantity = movement.product.stock_quantity

        if reverse_quantity > 0 and stock_quantity < reverse_quantity:
            raise ValidationError(
                f'Insufficient stock to undo. Available: {stock_quantity}, needed: {reverse_quantity}'
            )

        stock_before = _on_hand(movement.product, movement.variant)

        reverse_movement = StockMovement.objects.create(
            branch=movement.branch,
            product=movement.product,
            variant=movement.variant,
            movement_type='transfer',
            quantity=reverse_quantity,
            unit_cost=movement.unit_cost,
            total_cost=movement.total_cost,
            reference=f'UNDO-{movement.reference}',
            notes=f'UNDONE: {movement.notes}',
            user=user,
        )

        reverse_paired = None
        if paired_movement:
            reverse_paired = StockMovement.objects.create(
                branch=paired_movement.branch,
                product=paired_movement.product,
                variant=paired_movement.variant,
                movement_type='transfer',
                quantity=-paired_movement.quantity,
                unit_cost=paired_movement.unit_cost,
                total_cost=paired_movement.total_cost,
                reference=f'UNDO-{paired_movement.reference}',
                notes=f'UNDONE: {paired_movement.notes}',
                user=user,
            )
            movement.notes = f'UNDONE: {movement.notes}'
            movement.save(update_fields=['notes'])
            paired_movement.notes = f'UNDONE: {paired_movement.notes}'
            paired_movement.save(update_fields=['notes'])
        else:
            movement.notes = f'UNDONE: {movement.notes}'
            movement.save(update_fields=['notes'])

        if movement.variant_id:
            movement.variant.refresh_from_db(fields=['stock_quantity'])
        else:
            movement.product.refresh_from_db(fields=['stock_quantity'])
        self._audit_movement(
            reverse_movement,
            event='stock_undo',
            request=request,
            stock_before=stock_before,
            stock_after=_on_hand(movement.product, movement.variant),
            extra={
                'undone_movement_id': movement.id,
                'paired_undo_id': reverse_paired.id if reverse_paired else None,
            },
        )

        return movement, reverse_movement, reverse_paired
    
    def get_inventory_report(self, branch: Optional[Branch] = None,
                            product_id: Optional[int] = None) -> Dict[str, Any]:
        """Get inventory report with stock levels and movement aggregates."""
        from django.utils import timezone

        now = timezone.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        from products.status_rules import apply_operational_product_filter

        products_qs = apply_operational_product_filter(Product.objects.all())
        tracked_qs = products_qs.filter(track_stock=True)
        if product_id:
            tracked_qs = tracked_qs.filter(id=product_id)

        movements_qs = self.model.objects.all()
        if branch:
            movements_qs = movements_qs.filter(branch=branch)
        if product_id:
            movements_qs = movements_qs.filter(product_id=product_id)

        by_type = list(
            movements_qs.values('movement_type').annotate(
                total_quantity=Sum('quantity'),
                count=Count('id'),
            )
        )
        recent_movements = movements_qs.select_related(
            'product', 'variant', 'variant__size', 'variant__color'
        ).order_by('-created_at')[:20]

        total_value = tracked_qs.aggregate(
            total=Sum(F('stock_quantity') * F('cost')),
        )['total'] or 0

        return {
            'total_products': products_qs.count(),
            'tracked_products': tracked_qs.count(),
            'low_stock_count': tracked_qs.filter(
                stock_quantity__gt=0,
                stock_quantity__lte=F('low_stock_threshold'),
            ).count(),
            'out_of_stock_count': tracked_qs.filter(stock_quantity=0).count(),
            'total_inventory_value': total_value,
            'total_movements_today': movements_qs.filter(created_at__gte=start_of_day).count(),
            'total_movements_this_month': movements_qs.filter(created_at__gte=start_of_month).count(),
            'by_movement_type': by_type,
            'recent_movements': [
                {
                    'id': m.id,
                    'product': m.product.name,
                    'variant': str(m.variant) if m.variant_id else None,
                    'variant_id': m.variant_id,
                    'movement_type': m.movement_type,
                    'quantity': m.quantity,
                    'created_at': m.created_at,
                }
                for m in recent_movements
            ],
        }
