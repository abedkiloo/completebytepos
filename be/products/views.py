from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q, F, Sum, Count, Avg
from django.db import transaction
from django.http import HttpResponse
from django.core.exceptions import ValidationError
from .models import Category, Product, Size, Color, ProductVariant
from .serializers import (
    CategorySerializer, CategoryListSerializer,
    ProductSerializer, ProductListSerializer, ProductSearchSerializer,
    BulkProductUpdateSerializer, ProductStatisticsSerializer,
    SizeSerializer, ColorSerializer, ProductVariantSerializer
)
from .services import (
    ProductService, CategoryService, SizeService, ColorService, ProductVariantService
)
import csv
import json


class SizeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product sizes"""
    queryset = Size.objects.all()
    serializer_class = SizeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['display_order', 'name']
    ordering = ['display_order', 'name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.size_service = SizeService()
    
    def get_queryset(self):
        """Get queryset using service layer"""
        filters = {}
        if 'is_active' in self.request.query_params:
            filters['is_active'] = self.request.query_params.get('is_active')
        return self.size_service.build_queryset(filters)


class ColorViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product colors"""
    queryset = Color.objects.all()
    serializer_class = ColorSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color_service = ColorService()
    
    def get_queryset(self):
        """Get queryset using service layer"""
        filters = {}
        if 'is_active' in self.request.query_params:
            filters['is_active'] = self.request.query_params.get('is_active')
        return self.color_service.build_queryset(filters)


class ProductVariantViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product variants"""
    queryset = ProductVariant.objects.select_related('product', 'size', 'color').all()
    serializer_class = ProductVariantSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['sku', 'barcode', 'product__name']
    ordering_fields = ['product', 'size', 'color', 'sku']
    ordering = ['product', 'size', 'color']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.variant_service = ProductVariantService()
    
    def get_queryset(self):
        """Get queryset using service layer"""
        filters = {}
        if 'product' in self.request.query_params:
            filters['product'] = self.request.query_params.get('product')
        if 'is_active' in self.request.query_params:
            filters['is_active'] = self.request.query_params.get('is_active')
        return self.variant_service.build_queryset(filters)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().prefetch_related('products', 'children')
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_service = CategoryService()
    
    def get_queryset(self):
        """Get queryset using service layer"""
        filters = {}
        if 'is_active' in self.request.query_params:
            filters['is_active'] = self.request.query_params.get('is_active')
        if 'parent' in self.request.query_params:
            filters['parent'] = self.request.query_params.get('parent')
        return self.category_service.build_queryset(filters)

    def get_serializer_class(self):
        if self.action == 'list':
            return CategoryListSerializer
        return CategorySerializer

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in a category"""
        category = self.get_object()
        products = self.category_service.get_category_products(category.id, active_only=True)
        serializer = ProductListSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sku', 'barcode', 'description', 'supplier']
    ordering_fields = ['name', 'price', 'cost', 'created_at', 'stock_quantity', 'updated_at']
    ordering = ['name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.product_service = ProductService()

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['is_active', 'category', 'subcategory', 'low_stock', 
                     'out_of_stock', 'track_stock', 'supplier']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.product_service.build_queryset(filters)
    
    def perform_create(self, serializer):
        """Create product - thin view, business logic in service"""
        try:
            # Let serializer create the product (handles ManyToMany fields)
            product = serializer.save()
            
            # Use service to create variants if needed
            if product.has_variants:
                sizes = product.available_sizes.all()
                colors = product.available_colors.all()
                if sizes.exists() or colors.exists():
                    self.product_service.variant_service.create_variants_for_product(
                        product,
                        sizes=[s.id for s in sizes] if sizes.exists() else None,
                        colors=[c.id for c in colors] if colors.exists() else None
                    )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating product: {e}", exc_info=True)
            # Re-raise to let DRF handle it properly
            raise
    
    def perform_update(self, serializer):
        """Update product - serializer handles update, service handles variant changes"""
        # Let serializer update the product
        product = serializer.save()
        
        # Handle variant updates if variant settings changed
        # Check if variants need to be recreated
        sizes = product.available_sizes.all()
        colors = product.available_colors.all()
        
        if product.has_variants and (sizes.exists() or colors.exists()):
            # Delete existing variants and recreate
            ProductVariant.objects.filter(product=product).delete()
            self.product_service.variant_service.create_variants_for_product(
                product,
                sizes=[s.id for s in sizes] if sizes.exists() else None,
                colors=[c.id for c in colors] if colors.exists() else None
            )
        elif not product.has_variants:
            # Delete variants if has_variants is False
            ProductVariant.objects.filter(product=product).delete()

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Quick search endpoint for POS"""
        query = request.query_params.get('q', '').strip()
        limit = int(request.query_params.get('limit', 20))
        
        products = self.product_service.search_products(query, limit)
        serializer = ProductSearchSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get products with low stock"""
        products = self.product_service.get_low_stock_products()
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Get products that are out of stock"""
        products = self.product_service.get_out_of_stock_products()
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Bulk update products"""
        serializer = BulkProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_ids = serializer.validated_data['product_ids']
        update_data = serializer.validated_data['update_data']
        
        try:
            updated_count = self.product_service.bulk_update_products(product_ids, update_data)
            return Response({
                'message': f'{updated_count} products updated successfully',
                'updated_count': updated_count
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete products"""
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids:
            return Response(
                {'error': 'No product IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            deleted_count = self.product_service.bulk_delete_products(product_ids)
            return Response({
                'message': f'{deleted_count} products deleted successfully',
                'deleted_count': deleted_count
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Bulk activate products"""
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids:
            return Response(
                {'error': 'No product IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            updated_count = self.product_service.bulk_activate_products(product_ids)
            return Response({
                'message': f'{updated_count} products activated successfully',
                'updated_count': updated_count
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate products"""
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids:
            return Response(
                {'error': 'No product IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            updated_count = self.product_service.bulk_deactivate_products(product_ids)
            return Response({
                'message': f'{updated_count} products deactivated successfully',
                'updated_count': updated_count
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get product statistics"""
        try:
            stats = self.product_service.get_product_statistics()
            serializer = ProductStatisticsSerializer(stats)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting product statistics: {e}", exc_info=True)
            return Response(
                {'error': f'Error calculating statistics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export products to CSV with all fields matching the template format"""
        products = self.get_queryset()
        
        csv_data = self.product_service.export_products_to_csv(products)
        
        # Create response with BOM first for Excel compatibility, then CSV data
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
        # Write BOM for Excel compatibility (must be first)
        response.write('\ufeff')
        # Write CSV data
        response.write(csv_data)
        
        return response

    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        """Import products from CSV - supports template format"""
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        try:
            results = self.product_service.import_products_from_csv(file)
            
            message = f'Import completed: {results["created"]} created, {results["updated"]} updated'
            if results['errors']:
                message += f'. {len(results["errors"])} errors occurred.'
            
            return Response({
                'message': message,
                'created_count': results['created'],
                'updated_count': results['updated'],
                'errors': results['errors'][:10]  # Limit errors to first 10
            })
            
        except Exception as e:
            return Response(
                {'error': f'Import failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
