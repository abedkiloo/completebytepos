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
from .services import StockMovementService, inclusive_end_datetime, inclusive_start_datetime
from products.models import Product, ProductVariant
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
from utils.list_ordering import NameSavedOrderingFilter
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
    'set_sale_price': 'create',
    'set_layer_cost': 'update',
    'pending_prices': 'view',
    'set_on_hand': 'update',
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
    queryset = StockMovement.objects.all().select_related(
        'product', 'user', 'variant', 'variant__size', 'variant__color'
    )
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated, INVENTORY_PERMS]
    audit_module = 'inventory'
    # Stock movements are an audit log - the ONLY way to reverse one is via
    # the `undo` action which creates a compensating movement.
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    ordering = ['-created_at']
    filter_backends = [filters.SearchFilter, NameSavedOrderingFilter]
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
        use_catalog_cost = bool(serializer.validated_data.get('use_catalog_cost'))
        from products.catalog_access import user_is_super_admin

        if not user_is_super_admin(request.user):
            unit_cost = None
            use_catalog_cost = True
        
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
                'use_catalog_cost': use_catalog_cost,
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
                unit_cost=unit_cost,
                use_catalog_cost=use_catalog_cost,
                request=request,
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
        use_catalog_cost = bool(serializer.validated_data.get('use_catalog_cost'))
        unit_sell_price = serializer.validated_data.get('unit_sell_price')
        unit_mrp = serializer.validated_data.get('unit_mrp')
        price_mode = serializer.validated_data.get('price_mode') or 'new'
        reference = serializer.validated_data.get('reference', '')
        notes = serializer.validated_data.get('notes', '')
        
        current_branch = get_current_branch(request)
        reason = request.data.get('reason') or notes or 'Stock purchase'
        raw_rejected = request.data.get('rejected_change_id')
        try:
            rejected_change_id = int(raw_rejected) if raw_rejected not in (None, '', 0) else None
        except (TypeError, ValueError):
            rejected_change_id = None

        from approvals.inventory_integration import try_pending_stock_response
        from approvals.registry import ACTION_STOCK_PURCHASE

        apply_payload = {
            'product_id': product_id,
            'variant_id': variant_id,
            'quantity': quantity,
            'notes': notes,
            'unit_cost': str(unit_cost) if unit_cost is not None else None,
            'use_catalog_cost': use_catalog_cost,
            'unit_sell_price': (
                str(unit_sell_price) if unit_sell_price is not None else None
            ),
            'unit_mrp': str(unit_mrp) if unit_mrp is not None else None,
            'price_mode': price_mode,
            'branch_id': current_branch.id if current_branch else None,
            'reference': reference,
        }
        if rejected_change_id:
            from approvals.models import PendingChange
            from approvals.serializers import PendingChangeSerializer
            from approvals.service import correct_rejected_stock_purchase

            change = PendingChange.objects.filter(pk=rejected_change_id).first()
            if change is None:
                return Response(
                    {'error': 'That returned purchase was not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                updated = correct_rejected_stock_purchase(
                    change, request.user, apply_payload, reason,
                )
            except ValidationError as exc:
                if getattr(exc, 'message_dict', None):
                    return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
                messages = getattr(exc, 'messages', None) or [str(exc)]
                return Response(
                    {'error': messages[0]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    'message': 'Correction sent for approval, not yet in stock.',
                    'pending_change': PendingChangeSerializer(updated).data,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        pending_response = try_pending_stock_response(
            request,
            action_type=ACTION_STOCK_PURCHASE,
            apply_payload=apply_payload,
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
                reference=reference,
                unit_sell_price=unit_sell_price,
                use_catalog_cost=use_catalog_cost,
                request=request,
                price_mode=price_mode,
                unit_mrp=unit_mrp,
            )
            response_serializer = self.get_serializer(movement)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='pending-prices')
    def pending_prices(self, request):
        """
        Deliveries of one product that are still in stock.

        Args:
            request: Query ``product_id``, 1–2^31-1. Optional ``variant_id``
                for one size and colour. A variant product without it returns none.

        Returns:
            Up to 20 layers for that product or size. ``sale_price_pending`` is
            true when the selling price is unset. ``unit_cost`` is included
            only when this person may see cost of goods.
        """
        if not stock_purchases_allowed():
            return self._feature_disabled_response('Stock purchases')
        from inventory.models import StockLayer

        try:
            product_id = int(request.query_params.get('product_id') or 0)
        except (TypeError, ValueError):
            product_id = 0
        if product_id <= 0:
            return Response([])
        try:
            variant_id = int(request.query_params.get('variant_id') or 0)
        except (TypeError, ValueError):
            variant_id = 0
        if variant_id <= 0 and Product.objects.filter(pk=product_id, has_variants=True).exists():
            return Response([])
        rows = StockLayer.objects.filter(
            product_id=product_id,
            qty_remaining__gt=0,
        )
        if variant_id > 0:
            rows = rows.filter(variant_id=variant_id)
        rows = rows.order_by('-id')[:20]
        from products.cost_access import user_may_see_cost

        show_cost = user_may_see_cost(request.user)
        payload = []
        for row in rows:
            item = {
                'layer_id': row.id,
                'variant_id': row.variant_id,
                'quantity': row.qty_remaining,
                'unit_sell_price': str(row.unit_sell_price),
                'sale_price_pending': row.sale_price_pending,
            }
            if show_cost:
                item['unit_cost'] = str(row.unit_cost)
            payload.append(item)
        return Response(payload)

    @action(detail=False, methods=['post'], url_path='set-on-hand')
    def set_on_hand(self, request):
        """
        Set the shelf count for one product.

        Args:
            request: Body ``product_id``, ``quantity`` (0–1000000), and
                ``variant_id`` when the product has sizes and colours.
                Caller must be a manager or Super Admin.

        Returns:
            200 with the product id, the previous count, and the new count.
            Selling price and MRP are not changed.

        Raises:
            403: The caller is not a manager or Super Admin.
            400: The count is out of range.
        """
        from inventory.access import may_correct_on_hand

        if not may_correct_on_hand(request.user):
            return Response(
                {'error': 'Only a manager or Super Admin can correct the count.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            product_id = int(request.data.get('product_id') or 0)
            quantity = int(request.data.get('quantity'))
            raw_variant = request.data.get('variant_id')
            variant_id = int(raw_variant) if raw_variant not in (None, '', 0) else None
        except (TypeError, ValueError):
            return Response(
                {'error': 'Enter the count that is on the shelf.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        product = Product.objects.filter(pk=product_id).only(
            'id', 'stock_quantity', 'price', 'mrp', 'has_variants',
        ).first()
        if product is None:
            return Response({'error': 'Product not found'}, status=status.HTTP_400_BAD_REQUEST)
        variant = None
        if variant_id:
            variant = ProductVariant.objects.filter(pk=variant_id, product_id=product.id).first()
        before = int((variant.stock_quantity if variant else product.stock_quantity) or 0)
        price_before = variant.price if variant and variant.price is not None else product.price
        mrp_before = variant.mrp if variant and variant.mrp is not None else product.mrp
        try:
            self.stock_service.set_on_hand_count(
                product_id=product_id,
                quantity=quantity,
                notes=(request.data.get('notes') or '')[:500],
                user=request.user,
                branch=get_current_branch(request),
                request=request,
                variant_id=variant_id,
            )
        except ValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if variant is not None:
            variant.refresh_from_db(fields=['stock_quantity', 'price', 'mrp'])
            stock_now = variant.stock_quantity
            price_now = variant.price if variant.price is not None else product.price
            mrp_now = variant.mrp if variant.mrp is not None else product.mrp
        else:
            product.refresh_from_db(fields=['stock_quantity', 'price', 'mrp'])
            stock_now = product.stock_quantity
            price_now = product.price
            mrp_now = product.mrp
        return Response({
            'product_id': product.id,
            'variant_id': variant_id,
            'previous': before,
            'stock_quantity': stock_now,
            'price_unchanged': price_now == price_before,
            'mrp_unchanged': mrp_now == mrp_before,
        })

    @action(detail=False, methods=['post'], url_path='set-sale-price')
    def set_sale_price(self, request):
        """
        Set or change the selling price on pieces of one delivery still in stock.

        Args:
            request: Body ``layer_id``, ``unit_sell_price``, optional ``unit_mrp``.

        Returns:
            200 with the layer id and the new selling price.

        Raises:
            400: The delivery is missing or the price is not above 0.
        """
        if not stock_purchases_allowed():
            return self._feature_disabled_response('Stock purchases')
        from inventory.stock_layers import set_delivery_sale_price

        try:
            layer = set_delivery_sale_price(
                layer_id=int(request.data.get('layer_id') or 0),
                unit_sell_price=request.data.get('unit_sell_price'),
                unit_mrp=request.data.get('unit_mrp'),
            )
        except (ValidationError, TypeError, ValueError) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'layer_id': layer.id,
            'unit_sell_price': str(layer.unit_sell_price),
            'sale_price_pending': layer.sale_price_pending,
        })

    @action(detail=False, methods=['post'], url_path='set-layer-cost')
    def set_layer_cost(self, request):
        """
        Super Admin sets the cost on pieces of one delivery that are still in stock.

        Args:
            request: Body ``layer_id`` and ``unit_cost``. Caller must be a superuser.

        Returns:
            200 with the layer id and the new cost.

        Raises:
            403: The caller is not a superuser.
            400: The cost is not above 0.
        """
        if not stock_purchases_allowed():
            return self._feature_disabled_response('Stock purchases')
        from products.catalog_access import user_is_super_admin

        if not user_is_super_admin(request.user):
            return Response(
                {'error': 'Only a Super Admin can set the cost.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        from inventory.stock_layers import set_delivery_cost

        try:
            layer = set_delivery_cost(
                layer_id=int(request.data.get('layer_id') or 0),
                unit_cost=request.data.get('unit_cost'),
            )
        except (ValidationError, TypeError, ValueError) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'layer_id': layer.id,
            'unit_cost': str(layer.unit_cost),
        })

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
                user=request.user,
                request=request,
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
                movement, user=request.user, request=request
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
                    use_catalog_cost=bool(adj.get('use_catalog_cost')),
                    request=request,
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
        """Low-stock alert rows: simple products + individual low variants."""
        if not low_stock_alerts_allowed():
            return self._feature_disabled_response('Low-stock alerts')
        from products.stock_alerts import list_stock_alert_items

        return Response(list_stock_alert_items(kind='low_stock'))

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Out-of-stock alert rows: simple products + individual empty variants."""
        if not out_of_stock_alerts_allowed():
            return self._feature_disabled_response('Out-of-stock alerts')
        from products.stock_alerts import list_stock_alert_items

        return Response(list_stock_alert_items(kind='out_of_stock'))

    @action(detail=False, methods=['get'])
    def needs_reorder(self, request):
        """Same as low stock — one row per simple product or matching variant."""
        if not low_stock_alerts_allowed():
            return self._feature_disabled_response('Low-stock alerts')
        from products.stock_alerts import list_stock_alert_items

        items = list_stock_alert_items(kind='low_stock')
        items.sort(key=lambda row: (row.get('stock_quantity') or 0, row.get('name') or ''))
        return Response(items)

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
            queryset = queryset.filter(created_at__gte=inclusive_start_datetime(date_from))
        if date_to:
            queryset = queryset.filter(created_at__lte=inclusive_end_datetime(date_to))
        
        movements = queryset.values('movement_type').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity'),
            total_cost=Sum('total_cost')
        ).order_by('movement_type')
        
        return Response(list(movements))

    @action(detail=False, methods=['get'])
    def product_history(self, request):
        """Get stock movement history for a product (or one variant when applicable)."""
        from inventory.serializers import StockHistorySerializer
        from inventory.stock_history import product_stock_history_allowed
        from products.models import Product
        from utils.pagination import StandardResultsSetPagination

        if not product_stock_history_allowed(request.user):
            return Response(
                {
                    'error': (
                        'Product stock history is only available to admins '
                        'when enabled in inventory settings.'
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        product_id = request.query_params.get('product_id', None)
        variant_id = request.query_params.get('variant_id', None)

        if not product_id:
            return Response(
                {'error': 'product_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.only('id', 'has_variants').get(pk=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if product.has_variants and not variant_id:
            return Response(
                {
                    'error': (
                        'Select a variant to view stock history. '
                        'variant_id is required for products with variants.'
                    ),
                    'requires_variant': True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        movements = StockMovement.objects.filter(
            product_id=product_id
        ).select_related(
            'product', 'user', 'variant', 'variant__size', 'variant__color'
        ).order_by('-created_at')
        if variant_id:
            movements = movements.filter(variant_id=variant_id)

        # Lean serializer + pagination: busy variants (1000+ on hand) used to
        # nest full ProductListSerializer per row and time out / 500, which the
        # FE mistook for an admin-settings gate.
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(movements, request, view=self)
        serializer = StockHistorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
