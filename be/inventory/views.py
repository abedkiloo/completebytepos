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
from products.models import Product, ProductVariant
from settings.utils import get_current_branch, get_current_tenant, is_branch_support_enabled
import logging

logger = logging.getLogger(__name__)


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all().select_related('product', 'user')
    serializer_class = StockMovementSerializer
    ordering = ['-created_at']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product__name', 'product__sku', 'reference', 'notes']
    ordering_fields = ['created_at', 'quantity', 'movement_type']

    def get_queryset(self):
        queryset = StockMovement.objects.all().select_related('product', 'user', 'branch')
        
        # Filter by branch only if branch support is enabled
        if is_branch_support_enabled():
            # Filter by branch if specified (skip if show_all is true)
            show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
            branch_id = self.request.query_params.get('branch_id', None)
            
            if not show_all:
                if not branch_id:
                    # Try to get from current branch
                    current_branch = get_current_branch(self.request)
                    if current_branch:
                        branch_id = current_branch.id
                
                if branch_id:
                    queryset = queryset.filter(branch_id=branch_id)
        
        product_id = self.request.query_params.get('product', None)
        movement_type = self.request.query_params.get('movement_type', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset

    @transaction.atomic
    @action(detail=False, methods=['post'])
    def adjust(self, request):
        """Adjust stock for a product or variant"""
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        variant_id = serializer.validated_data.get('variant_id')
        quantity = serializer.validated_data['quantity']
        notes = serializer.validated_data.get('notes', '')
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                return Response(
                    {'error': 'Variant not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if not product.track_stock:
            return Response(
                {'error': 'Product does not track stock'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current branch
        current_branch = get_current_branch(request)
        
        # Create stock movement (adjustment)
        movement = StockMovement.objects.create(
            branch=current_branch,
            product=product,
            variant=variant,
            movement_type='adjustment',
            quantity=quantity,  # Can be positive or negative
            notes=notes,
            user=request.user,
            reference=f'ADJ-{variant.sku if variant else product.sku}'
        )
        
        # Stock is updated automatically in StockMovement.save()
        
        response_serializer = self.get_serializer(movement)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    @action(detail=False, methods=['post'])
    def purchase(self, request):
        """Record stock purchase for product or variant"""
        serializer = StockPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        variant_id = serializer.validated_data.get('variant_id')
        quantity = serializer.validated_data['quantity']
        unit_cost = serializer.validated_data.get('unit_cost')
        reference = serializer.validated_data.get('reference', '')
        notes = serializer.validated_data.get('notes', '')
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                return Response(
                    {'error': 'Variant not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if not product.track_stock:
            return Response(
                {'error': 'Product does not track stock'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine unit cost
        if not unit_cost:
            if variant and variant.cost:
                unit_cost = variant.cost
            else:
                unit_cost = product.cost
        
        # Get current branch
        current_branch = get_current_branch(request)
        
        # Create stock movement (purchase)
        movement = StockMovement.objects.create(
            branch=current_branch,
            product=product,
            variant=variant,
            movement_type='purchase',
            quantity=quantity,
            unit_cost=unit_cost,
            notes=notes,
            user=request.user,
            reference=reference or f'PUR-{variant.sku if variant else product.sku}'
        )
        
        response_serializer = self.get_serializer(movement)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

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
        """Get inventory report"""
        today = timezone.now().date()
        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))
        
        # Get all products
        all_products = Product.objects.filter(is_active=True)
        tracked_products = all_products.filter(track_stock=True)
        
        # Calculate statistics
        stats = {
            'total_products': all_products.count(),
            'tracked_products': tracked_products.count(),
            'low_stock_count': tracked_products.filter(
                stock_quantity__lte=F('low_stock_threshold')
            ).count(),
            'out_of_stock_count': tracked_products.filter(stock_quantity=0).count(),
            'total_inventory_value': float(
                tracked_products.aggregate(
                    total=Sum(F('stock_quantity') * F('cost'))
                )['total'] or 0
            ),
            'total_movements_today': StockMovement.objects.filter(
                created_at__gte=start_of_day
            ).count(),
            'total_movements_this_month': StockMovement.objects.filter(
                created_at__gte=start_of_month
            ).count(),
        }
        
        serializer = InventoryReportSerializer(stats)
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
