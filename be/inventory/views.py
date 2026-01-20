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
        """Record stock transfer (future: between branches)"""
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']
        reference = serializer.validated_data.get('reference', '')
        notes = serializer.validated_data.get('notes', '')
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not product.track_stock:
            return Response(
                {'error': 'Product does not track stock'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if product.stock_quantity < quantity:
            return Response(
                {'error': f'Insufficient stock. Available: {product.stock_quantity}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current branch
        current_branch = get_current_branch(request)
        
        # Create stock movement (transfer - reduces stock)
        movement = StockMovement.objects.create(
            branch=current_branch,
            product=product,
            movement_type='transfer',
            quantity=-quantity,  # Negative to reduce stock
            notes=notes,
            user=request.user,
            reference=reference or f'TRF-{product.sku}'
        )
        
        response_serializer = self.get_serializer(movement)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

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
