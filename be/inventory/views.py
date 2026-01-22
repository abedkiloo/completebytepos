from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import F, Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import StockMovement
from .serializers import (
    StockMovementSerializer, StockAdjustmentSerializer,
    StockPurchaseSerializer, StockTransferSerializer,
    BulkStockAdjustmentSerializer, InventoryReportSerializer
)
from .services import StockMovementService
from products.models import Product, ProductVariant
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all().select_related('product', 'user')
    serializer_class = StockMovementSerializer
    ordering = ['-created_at']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product__name', 'product__sku', 'reference', 'notes']
    ordering_fields = ['created_at', 'quantity', 'movement_type']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stock_service = StockMovementService()

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['branch_id', 'show_all', 'product', 'movement_type', 'date_from', 'date_to']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.stock_service.build_queryset(filters, request=self.request)

    @transaction.atomic
    @action(detail=False, methods=['post'])
    def adjust(self, request):
        """Adjust stock for a product or variant - thin view, business logic in service"""
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        variant_id = serializer.validated_data.get('variant_id')
        quantity = serializer.validated_data['quantity']
        notes = serializer.validated_data.get('notes', '')
        unit_cost = serializer.validated_data.get('unit_cost')
        
        current_branch = get_current_branch(request)
        
        try:
            movement = self.stock_service.adjust_stock(
                product_id=product_id,
                variant_id=variant_id,
                quantity=quantity,
                notes=notes,
                user=request.user,
                branch=current_branch,
                unit_cost=unit_cost
            )
            response_serializer = self.get_serializer(movement)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @transaction.atomic
    @action(detail=False, methods=['post'])
    def purchase(self, request):
        """Record stock purchase - thin view, business logic in service"""
        serializer = StockPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        variant_id = serializer.validated_data.get('variant_id')
        quantity = serializer.validated_data['quantity']
        unit_cost = serializer.validated_data.get('unit_cost')
        reference = serializer.validated_data.get('reference', '')
        notes = serializer.validated_data.get('notes', '')
        
        current_branch = get_current_branch(request)
        
        try:
            movement = self.stock_service.purchase_stock(
                product_id=product_id,
                variant_id=variant_id,
                quantity=quantity,
                unit_cost=unit_cost,
                notes=notes,
                user=request.user,
                branch=current_branch,
                reference=reference
            )
            response_serializer = self.get_serializer(movement)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @transaction.atomic
    @action(detail=False, methods=['post'])
    def transfer(self, request):
        """Record stock transfer between branches"""
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']
        to_branch_id = serializer.validated_data['to_branch_id']
        reference = serializer.validated_data.get('reference', '')
        notes = serializer.validated_data.get('notes', '')
        
        # Get branches
        from settings.models import Branch
        from_branch = get_current_branch(request)
        
        # Validate that branch support is enabled and from_branch exists
        if not is_branch_support_enabled() or from_branch is None:
            return Response(
                {'error': 'Branch support must be enabled and a source branch must be selected for stock transfers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            to_branch = Branch.objects.get(id=to_branch_id, is_active=True)
        except Branch.DoesNotExist:
            return Response(
                {'error': 'Destination branch not found or inactive'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if from_branch == to_branch:
            return Response(
                {'error': 'Source and destination branches must be different'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use service to transfer stock
        service = StockMovementService()
        try:
            # Build notes with branch names (both are guaranteed to exist at this point)
            transfer_notes = notes or f'Transfer from {from_branch.name} to {to_branch.name}'
            movements = service.transfer_stock(
                product_id=product_id,
                variant_id=None,
                quantity=quantity,
                from_branch=from_branch,
                to_branch=to_branch,
                notes=transfer_notes,
                user=request.user
            )
            
            # Update reference if provided
            # Use update_fields to prevent stock recalculation when only updating reference
            if reference:
                for movement in movements:
                    movement.reference = reference
                    movement.save(update_fields=['reference'])
            
            response_serializer = self.get_serializer(movements, many=True)
            return Response({
                'movements': response_serializer.data,
                'message': f'Stock transferred successfully to {to_branch.name}'
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def undo(self, request, pk=None):
        """Undo a stock transfer by reversing the movements"""
        try:
            movement = self.get_object()
        except StockMovement.DoesNotExist:
            return Response(
                {'error': 'Stock movement not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only allow undoing transfer movements
        if movement.movement_type != 'transfer':
            return Response(
                {'error': 'Can only undo transfer movements'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already undone
        if movement.notes and 'UNDONE' in movement.notes:
            return Response(
                {'error': 'This transfer has already been undone'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find the paired movement (if transfer between branches)
        # For outbound transfers, find the inbound; for inbound, find the outbound
        paired_movement = None
        
        # Primary method: Use shared reference ID to pair movements
        # New transfers use format: TRF-{transfer_id}-OUT and TRF-{transfer_id}-IN
        # This works even with custom notes
        if movement.reference and movement.reference.startswith('TRF-'):
            import re
            # Extract transfer ID from reference (e.g., "TRF-ABC12345-OUT" -> "TRF-ABC12345")
            ref_match = re.match(r'^(TRF-[A-Z0-9]+)-OUT$', movement.reference)
            if ref_match:
                # This is an outbound movement, find the inbound with matching transfer ID
                transfer_id = ref_match.group(1)
                paired_movement = StockMovement.objects.filter(
                    reference=f'{transfer_id}-IN',
                    movement_type='transfer',
                    product=movement.product,
                    variant=movement.variant
                ).exclude(id=movement.id).first()
            else:
                ref_match = re.match(r'^(TRF-[A-Z0-9]+)-IN$', movement.reference)
                if ref_match:
                    # This is an inbound movement, find the outbound with matching transfer ID
                    transfer_id = ref_match.group(1)
                    paired_movement = StockMovement.objects.filter(
                        reference=f'{transfer_id}-OUT',
                        movement_type='transfer',
                        product=movement.product,
                        variant=movement.variant
                    ).exclude(id=movement.id).first()
        
        # Fallback method: Use note patterns and timing for older transfers without shared reference
        # This maintains backward compatibility with existing transfers
        if not paired_movement:
            if movement.quantity < 0:  # Outbound
                # Build filter query - only include branch filter if branch exists
                filter_kwargs = {
                    'product': movement.product,
                    'variant': movement.variant,
                    'movement_type': 'transfer',
                    'quantity': -movement.quantity,  # Positive quantity
                    'created_at__gte': movement.created_at - timedelta(seconds=5),
                    'created_at__lte': movement.created_at + timedelta(seconds=5),
                }
                # Only filter by branch name if branch exists (avoid empty string which matches all)
                if movement.branch and movement.branch.name:
                    filter_kwargs['notes__icontains'] = movement.branch.name
                
                paired_movement = StockMovement.objects.filter(**filter_kwargs).exclude(id=movement.id).first()
            else:  # Inbound
                # For inbound movements, find the paired outbound movement
                # Inbound movements have notes like "Transfer in from {from_branch.name}"
                # Outbound movements have notes like "Transfer out to {to_branch.name}"
                # We need to find the outbound movement from the source branch
                
                # First, try to extract source branch from inbound movement notes
                if movement.notes:
                    import re
                    # Match pattern: "Transfer in from {branch_name}" or custom notes
                    # The standard format is: "Transfer in from {from_branch.name}"
                    # We need to capture the full branch name, including spaces (e.g., "Main Branch")
                    # Use greedy match (.+) to capture everything after "Transfer in from " until end of string
                    # This correctly handles multi-word branch names like "Main Branch", "Downtown Store", etc.
                    match = re.search(r'Transfer in from (.+)$', movement.notes, re.IGNORECASE)
                    
                    if match:
                        source_branch_name = match.group(1).strip()
                        # Find outbound movement from the source branch with matching quantity and timing
                        paired_movement = StockMovement.objects.filter(
                            product=movement.product,
                            variant=movement.variant,
                            movement_type='transfer',
                            quantity=-movement.quantity,  # Negative quantity (outbound)
                            created_at__gte=movement.created_at - timedelta(seconds=5),
                            created_at__lte=movement.created_at + timedelta(seconds=5),
                            branch__name__icontains=source_branch_name,
                            notes__icontains='Transfer out'
                        ).exclude(id=movement.id).first()
                
                # Fallback: if not found by branch name, search by "Transfer out" pattern
                # This handles cases where notes format might be different
                if not paired_movement:
                    paired_movement = StockMovement.objects.filter(
                        product=movement.product,
                        variant=movement.variant,
                        movement_type='transfer',
                        quantity=-movement.quantity,  # Negative quantity (outbound)
                        created_at__gte=movement.created_at - timedelta(seconds=5),
                        created_at__lte=movement.created_at + timedelta(seconds=5),
                        notes__icontains='Transfer out'  # Outbound movements have "Transfer out to {branch_name}"
                    ).exclude(id=movement.id).first()
        
        # Reverse the movements
        service = StockMovementService()
        try:
            # Reverse the current movement
            reverse_quantity = -movement.quantity
            if movement.variant:
                stock_quantity = movement.variant.stock_quantity
            else:
                stock_quantity = movement.product.stock_quantity
            
            # Check if we have enough stock to reverse
            if reverse_quantity > 0 and stock_quantity < reverse_quantity:
                return Response(
                    {'error': f'Insufficient stock to undo. Available: {stock_quantity}, needed: {reverse_quantity}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create reverse movement
            # Note: StockMovement.save() automatically updates stock based on movement_type and quantity
            # No need to manually update stock here - it's handled by the model's save() method
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
                user=request.user
            )
            
            # If there's a paired movement, reverse it too
            # Note: StockMovement.save() automatically updates stock based on movement_type and quantity
            # No need to manually update stock here - it's handled by the model's save() method
            if paired_movement:
                reverse_paired_quantity = -paired_movement.quantity
                reverse_paired_movement = StockMovement.objects.create(
                    branch=paired_movement.branch,
                    product=paired_movement.product,
                    variant=paired_movement.variant,
                    movement_type='transfer',
                    quantity=reverse_paired_quantity,
                    unit_cost=paired_movement.unit_cost,
                    total_cost=paired_movement.total_cost,
                    reference=f'UNDO-{paired_movement.reference}',
                    notes=f'UNDONE: {paired_movement.notes}',
                    user=request.user
                )
                
                # Mark both as undone
                # Use update_fields to prevent stock recalculation when only updating notes
                movement.notes = f'UNDONE: {movement.notes}'
                movement.save(update_fields=['notes'])
                paired_movement.notes = f'UNDONE: {paired_movement.notes}'
                paired_movement.save(update_fields=['notes'])
                
                return Response({
                    'message': 'Transfer undone successfully',
                    'movements': [
                        self.get_serializer(reverse_movement).data,
                        self.get_serializer(reverse_paired_movement).data
                    ]
                }, status=status.HTTP_200_OK)
            
            # Mark as undone
            # Use update_fields to prevent stock recalculation when only updating notes
            movement.notes = f'UNDONE: {movement.notes}'
            movement.save(update_fields=['notes'])
            
            return Response({
                'message': 'Transfer undone successfully',
                'movement': self.get_serializer(reverse_movement).data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error undoing transfer: {e}", exc_info=True)
            return Response(
                {'error': f'Failed to undo transfer: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @transaction.atomic
    @action(detail=False, methods=['post'])
    def bulk_adjust(self, request):
        """Bulk stock adjustments"""
        serializer = BulkStockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        adjustments = serializer.validated_data['adjustments']
        created_movements = []
        errors = []
        
        for idx, adj in enumerate(adjustments):
            try:
                product_id = adj.get('product_id')
                quantity = adj.get('quantity')
                notes = adj.get('notes', '')
                
                if not product_id or quantity is None:
                    errors.append(f"Adjustment {idx + 1}: Missing product_id or quantity")
                    continue
                
                try:
                    product = Product.objects.get(id=product_id)
                except Product.DoesNotExist:
                    errors.append(f"Adjustment {idx + 1}: Product not found")
                    continue
                
                if not product.track_stock:
                    errors.append(f"Adjustment {idx + 1}: Product does not track stock")
                    continue
                
                # Get current branch
                current_branch = get_current_branch(request)
                
                movement = StockMovement.objects.create(
                    branch=current_branch,
                    product=product,
                    movement_type='adjustment',
                    quantity=quantity,
                    notes=notes,
                    user=request.user,
                    reference=f'BULK-ADJ-{product.sku}'
                )
                created_movements.append(movement)
                
            except Exception as e:
                errors.append(f"Adjustment {idx + 1}: {str(e)}")
        
        response_serializer = self.get_serializer(created_movements, many=True)
        return Response({
            'created': len(created_movements),
            'errors': errors,
            'movements': response_serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get all products with low stock"""
        from products.serializers import ProductListSerializer
        
        products = Product.objects.filter(
            stock_quantity__lte=F('low_stock_threshold'),
            is_active=True,
            track_stock=True
        )
        serializer = ProductListSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Get all products that are out of stock"""
        from products.serializers import ProductListSerializer
        
        products = Product.objects.filter(
            stock_quantity=0,
            is_active=True,
            track_stock=True
        )
        serializer = ProductListSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def needs_reorder(self, request):
        """Get all products that need reordering"""
        from products.serializers import ProductListSerializer
        
        products = Product.objects.filter(
            stock_quantity__lte=F('low_stock_threshold'),
            is_active=True,
            track_stock=True
        ).order_by('stock_quantity')
        
        serializer = ProductListSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def report(self, request):
        """Get inventory report - thin view, business logic in service"""
        current_branch = get_current_branch(request)
        product_id = request.query_params.get('product_id')
        if product_id:
            try:
                product_id = int(product_id)
            except (ValueError, TypeError):
                product_id = None
        
        report = self.stock_service.get_inventory_report(
            branch=current_branch,
            product_id=product_id
        )
        serializer = InventoryReportSerializer(report)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def movements_by_type(self, request):
        """Get movements grouped by type"""
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        
        queryset = StockMovement.objects.all()
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        movements = queryset.values('movement_type').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity'),
            total_cost=Sum('total_cost')
        ).order_by('movement_type')
        
        return Response(list(movements))

    @action(detail=False, methods=['get'])
    def product_history(self, request):
        """Get stock movement history for a specific product"""
        product_id = request.query_params.get('product_id', None)
        
        if not product_id:
            return Response(
                {'error': 'product_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            movements = StockMovement.objects.filter(
                product_id=product_id
            ).select_related('product', 'user').order_by('-created_at')
            
            serializer = self.get_serializer(movements, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
