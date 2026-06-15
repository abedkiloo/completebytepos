from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
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
from accounts.permissions import RequirePermPerAction
from utils.audit_mixin import AuditedModelViewSetMixin
from django.core.exceptions import ValidationError
from inventory.access import (
    inventory_report_allowed,
    low_stock_alerts_allowed,
    movement_undo_allowed,
    out_of_stock_alerts_allowed,
    stock_adjustments_allowed,
    stock_movements_allowed,
    stock_purchases_allowed,
    stock_transfers_allowed,
)
from inventory.module_settings import inventory_show_movement_cost
import logging

logger = logging.getLogger(__name__)


# Stock movements get gated against the `inventory` module. The custom @action
# endpoints map to permission verbs that match their intent:
#   adjust/purchase/transfer  -> 'create' (they create a StockMovement)
#   undo                       -> 'update' (it reverses a previous movement)
#   bulk_adjust                -> 'create'
#   low_stock/out_of_stock/needs_reorder/report/movements_by_type/product_history -> 'view'
INVENTORY_PERMS = RequirePermPerAction('inventory', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
    'adjust': 'create',
    'purchase': 'create',
    'transfer': 'create',
    'undo': 'update',
    'bulk_adjust': 'create',
    'low_stock': 'view',
    'out_of_stock': 'view',
    'needs_reorder': 'view',
    'report': 'view',
    'movements_by_type': 'view',
    'product_history': 'view',
})


class StockMovementViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = StockMovement.objects.all().select_related('product', 'user')
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated, INVENTORY_PERMS]
    audit_module = 'inventory'
    # Stock movements are an audit log - the ONLY way to reverse one is via
    # the `undo` action which creates a compensating movement.
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    ordering = ['-created_at']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product__name', 'product__sku', 'reference', 'notes']
    ordering_fields = ['created_at', 'quantity', 'movement_type']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stock_service = StockMovementService()

    @staticmethod
    def _feature_disabled_response(feature_label: str):
        return Response(
            {'error': f'{feature_label} is disabled in store settings.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    def list(self, request, *args, **kwargs):
        if not stock_movements_allowed():
            return self._feature_disabled_response('Stock movements')
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not stock_movements_allowed():
            return self._feature_disabled_response('Stock movements')
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not stock_movements_allowed():
            return self._feature_disabled_response('Stock movements')
        return super().create(request, *args, **kwargs)

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
        if not stock_adjustments_allowed():
            return self._feature_disabled_response('Stock adjustments')
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        variant_id = serializer.validated_data.get('variant_id')
        quantity = serializer.validated_data['quantity']
        notes = serializer.validated_data.get('notes', '')
        unit_cost = serializer.validated_data.get('unit_cost')
        
        current_branch = get_current_branch(request)
        reason = request.data.get('reason') or notes or 'Stock adjustment'

        from approvals.inventory_integration import try_pending_stock_response
        from approvals.registry import ACTION_STOCK_ADJUST

        pending_response = try_pending_stock_response(
            request,
            action_type=ACTION_STOCK_ADJUST,
            apply_payload={
                'product_id': product_id,
                'variant_id': variant_id,
                'quantity': quantity,
                'notes': notes,
                'unit_cost': str(unit_cost) if unit_cost is not None else None,
                'branch_id': current_branch.id if current_branch else None,
            },
            reason=reason,
        )
        if pending_response is not None:
            return pending_response

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
            from utils.audit_events import log_stock_movement_event

            log_stock_movement_event(
                request,
                movement,
                event='stock_adjust',
                payload={
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'notes': notes,
                },
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
        if not stock_purchases_allowed():
            return self._feature_disabled_response('Stock purchases')
        serializer = StockPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        variant_id = serializer.validated_data.get('variant_id')
        quantity = serializer.validated_data['quantity']
        unit_cost = serializer.validated_data.get('unit_cost')
        reference = serializer.validated_data.get('reference', '')
        notes = serializer.validated_data.get('notes', '')
        
        current_branch = get_current_branch(request)
        reason = request.data.get('reason') or notes or 'Stock purchase'

        from approvals.inventory_integration import try_pending_stock_response
        from approvals.registry import ACTION_STOCK_PURCHASE

        pending_response = try_pending_stock_response(
            request,
            action_type=ACTION_STOCK_PURCHASE,
            apply_payload={
                'product_id': product_id,
                'variant_id': variant_id,
                'quantity': quantity,
                'notes': notes,
                'unit_cost': str(unit_cost) if unit_cost is not None else None,
                'branch_id': current_branch.id if current_branch else None,
                'reference': reference,
            },
            reason=reason,
        )
        if pending_response is not None:
            return pending_response

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
            from utils.audit_events import log_stock_movement_event

            log_stock_movement_event(
                request,
                movement,
                event='stock_purchase',
                payload={
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'unit_cost': str(unit_cost) if unit_cost is not None else None,
                    'reference': reference,
                },
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
        if not stock_transfers_allowed():
            return self._feature_disabled_response('Stock transfers')
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

        reason = request.data.get('reason') or notes or 'Stock transfer'
        transfer_notes = notes or f'Transfer from {from_branch.name} to {to_branch.name}'

        from approvals.inventory_integration import try_pending_stock_response
        from approvals.registry import ACTION_STOCK_TRANSFER

        pending_response = try_pending_stock_response(
            request,
            action_type=ACTION_STOCK_TRANSFER,
            apply_payload={
                'product_id': product_id,
                'variant_id': None,
                'quantity': quantity,
                'notes': transfer_notes,
                'branch_id': from_branch.id,
                'to_branch_id': to_branch.id,
                'reference': reference,
            },
            reason=reason,
        )
        if pending_response is not None:
            return pending_response

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

            from utils.audit_events import log_stock_movement_event

            for movement in movements:
                log_stock_movement_event(
                    request,
                    movement,
                    event='stock_transfer',
                    payload={
                        'product_id': product_id,
                        'from_branch_id': from_branch.id,
                        'to_branch_id': to_branch.id,
                    },
                )

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
        """Undo a stock transfer by reversing the movements (service layer)."""
        if not movement_undo_allowed():
            return self._feature_disabled_response('Movement undo')
        try:
            movement = self.get_object()
        except StockMovement.DoesNotExist:
            return Response(
                {'error': 'Stock movement not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            _, reverse_movement, reverse_paired = self.stock_service.undo_transfer(
                movement, user=request.user
            )
            from utils.audit_events import log_stock_movement_event

            log_stock_movement_event(
                request,
                reverse_movement,
                event='stock_undo',
                payload={'original_movement_id': movement.id},
            )
            if reverse_paired:
                log_stock_movement_event(
                    request,
                    reverse_paired,
                    event='stock_undo',
                    payload={'original_movement_id': movement.id},
                )
            if reverse_paired:
                return Response({
                    'message': 'Transfer undone successfully',
                    'movements': [
                        self.get_serializer(reverse_movement).data,
                        self.get_serializer(reverse_paired).data,
                    ],
                }, status=status.HTTP_200_OK)
            return Response({
                'message': 'Transfer undone successfully',
                'movement': self.get_serializer(reverse_movement).data,
            }, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Error undoing transfer: {e}', exc_info=True)
            return Response(
                {'error': f'Failed to undo transfer: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @transaction.atomic
    @action(detail=False, methods=['post'])
    def bulk_adjust(self, request):
        """Bulk stock adjustments"""
        if not stock_adjustments_allowed():
            return self._feature_disabled_response('Stock adjustments')
        serializer = BulkStockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        adjustments = serializer.validated_data['adjustments']
        reason = request.data.get('reason') or 'Bulk stock adjustment'

        from approvals.permissions import is_maker_checker_enabled
        from approvals.service import route_bulk_stock_adjustments

        if is_maker_checker_enabled():
            current_branch = get_current_branch(request)
            payload_lines = []
            for adj in adjustments:
                line = dict(adj)
                if current_branch:
                    line['branch_id'] = current_branch.id
                payload_lines.append(line)
            pending_rows = route_bulk_stock_adjustments(
                request,
                adjustments=payload_lines,
                reason=reason,
            )
            if pending_rows:
                from approvals.serializers import PendingChangeSerializer

                return Response(
                    {
                        'message': 'Change submitted for approval, not yet active.',
                        'pending_changes': PendingChangeSerializer(
                            pending_rows, many=True
                        ).data,
                        'batch_id': pending_rows[0].batch_id,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

        created_movements = []
        errors = []

        for idx, adj in enumerate(adjustments):
            try:
                product_id = adj.get('product_id')
                variant_id = adj.get('variant_id')
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
                
                if product.has_variants and not variant_id:
                    errors.append(
                        f"Adjustment {idx + 1}: variant_id is required for variant products"
                    )
                    continue
                
                # Get current branch
                current_branch = get_current_branch(request)
                
                movement = self.stock_service.adjust_stock(
                    product_id=product_id,
                    variant_id=variant_id,
                    quantity=int(quantity),
                    notes=notes,
                    user=request.user,
                    branch=current_branch,
                    unit_cost=adj.get('unit_cost'),
                )
                created_movements.append(movement)
                from utils.audit_events import log_stock_movement_event

                log_stock_movement_event(
                    request,
                    movement,
                    event='stock_adjust',
                    payload={
                        'product_id': product_id,
                        'variant_id': variant_id,
                        'bulk': True,
                    },
                )

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
        if not low_stock_alerts_allowed():
            return self._feature_disabled_response('Low-stock alerts')
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
        if not out_of_stock_alerts_allowed():
            return self._feature_disabled_response('Out-of-stock alerts')
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
        if not low_stock_alerts_allowed():
            return self._feature_disabled_response('Low-stock alerts')
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
        if not inventory_report_allowed():
            return self._feature_disabled_response('Inventory overview report')
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
        if not stock_movements_allowed():
            return self._feature_disabled_response('Stock movements')
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
        if not stock_movements_allowed():
            return self._feature_disabled_response('Stock movements')
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
