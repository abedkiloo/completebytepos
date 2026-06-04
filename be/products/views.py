from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, F, Sum, Count, Avg
from django.db import transaction
from django.http import HttpResponse
from django.core.exceptions import ValidationError
from .models import Category, Product, Size, Color, ProductVariant, UnitOfMeasure
from .serializers import (
    CategorySerializer, CategoryListSerializer,
    ProductSerializer, ProductListSerializer, ProductSearchSerializer,
    BulkProductUpdateSerializer, ProductStatisticsSerializer,
    SizeSerializer, ColorSerializer, ProductVariantSerializer,
    UnitOfMeasureSerializer,
)
from .services import (
    ProductService, CategoryService, SizeService, ColorService, ProductVariantService
)
from accounts.permissions import HasPermission, RequirePermPerAction
from settings.feature_flags import is_product_variants_enabled
from products.module_settings import (
    products_bulk_operations_enabled,
    products_csv_import_export_enabled,
)
from utils.audit_mixin import AuditedModelViewSetMixin
import csv
import json


# Permission maps. Each entry maps a DRF action (built-in or @action name) to
# the permission action verb checked against the user's role/custom_role.
# @action endpoints not listed here are denied by RequirePermPerAction
# (fail-closed).
PRODUCTS_PERMS = RequirePermPerAction('products', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
    'search': 'view',
    'low_stock': 'view',
    'out_of_stock': 'view',
    'statistics': 'view',
    'export': 'export',
    'import_csv': 'import',
    'bulk_update': 'update',
    'bulk_delete': 'delete',
    'bulk_activate': 'update',
    'bulk_deactivate': 'update',
})

CATEGORIES_PERMS = RequirePermPerAction('categories', {
    'list': 'view',
    'retrieve': 'view',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
    # CategoryViewSet.products is a read action listing products in a category
    'products': 'view',
})


class SizeViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """ViewSet for managing product sizes"""
    queryset = Size.objects.all()
    serializer_class = SizeSerializer
    permission_classes = [IsAuthenticated, PRODUCTS_PERMS]
    audit_module = 'product_sizes'
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


class UnitOfMeasureViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """Units of measure — list for all users; create for super admins."""

    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [IsAuthenticated, PRODUCTS_PERMS]
    audit_module = 'product_units'
    ordering = ['display_order', 'label']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        from accounts.permissions import IsSuperAdmin
        return [IsAuthenticated(), IsSuperAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('is_active') == 'true':
            qs = qs.filter(is_active=True)
        return qs

    def list(self, request, *args, **kwargs):
        from products.units import list_active_units

        if request.query_params.get('format') == 'options':
            return Response({'results': list_active_units()})
        return super().list(request, *args, **kwargs)

class ColorViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """ViewSet for managing product colors"""
    queryset = Color.objects.all()
    serializer_class = ColorSerializer
    permission_classes = [IsAuthenticated, PRODUCTS_PERMS]
    audit_module = 'product_colors'
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


class ProductVariantViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """ViewSet for managing product variants"""
    queryset = ProductVariant.objects.select_related('product', 'size', 'color').all()
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, PRODUCTS_PERMS]
    audit_module = 'product_variants'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['sku', 'barcode', 'product__name']
    ordering_fields = ['product', 'size', 'color', 'sku']
    ordering = ['product', 'size', 'color']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.variant_service = ProductVariantService()

    def get_permissions(self):
        if getattr(self, 'action', None) == 'destroy':
            from approvals.permissions import is_maker_checker_enabled

            if is_maker_checker_enabled():
                return [IsAuthenticated(), HasPermission('products', 'update')]
        return [IsAuthenticated(), PRODUCTS_PERMS()]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        from approvals.variant_integration import (
            queue_variant_sensitive_update,
            split_variant_payload,
        )
        from approvals.serializers import PendingChangeSerializer
        from approvals.permissions import is_maker_checker_enabled

        validated = dict(serializer.validated_data)
        submitted_keys = set(serializer.initial_data.keys())
        sensitive, _immediate = split_variant_payload(
            validated,
            submitted_keys=submitted_keys,
        )
        try:
            pending = queue_variant_sensitive_update(request, instance, sensitive)
        except ValidationError as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            if hasattr(exc, 'message_dict'):
                raise DRFValidationError(exc.message_dict)
            raise DRFValidationError(str(exc))

        if pending is not None:
            for key in sensitive:
                serializer.validated_data.pop(key, None)
        elif is_maker_checker_enabled() and sensitive:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(
                {'reason': 'A reason is required for variant price, stock, or status changes.'}
            )

        if serializer.validated_data:
            self.perform_update(serializer)
        elif pending is None:
            return Response(serializer.data)

        instance.refresh_from_db()
        data = self.get_serializer(instance).data
        if pending:
            return Response(
                {
                    'message': 'Change submitted for approval, not yet active.',
                    'pending_change': PendingChangeSerializer(pending).data,
                    'variant': data,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        from approvals.variant_integration import queue_variant_delete
        from approvals.permissions import is_maker_checker_enabled
        from approvals.serializers import PendingChangeSerializer

        if is_maker_checker_enabled():
            instance = self.get_object()
            try:
                pending = queue_variant_delete(request, instance)
            except ValidationError as exc:
                from rest_framework.exceptions import ValidationError as DRFValidationError

                if hasattr(exc, 'message_dict'):
                    raise DRFValidationError(exc.message_dict)
                raise DRFValidationError(str(exc))
            return Response(
                {
                    'message': 'Change submitted for approval, not yet active.',
                    'pending_change': PendingChangeSerializer(pending).data,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return super().destroy(request, *args, **kwargs)
    
    def get_queryset(self):
        """Get queryset using service layer"""
        filters = {}
        if 'product' in self.request.query_params:
            filters['product'] = self.request.query_params.get('product')
        if 'is_active' in self.request.query_params:
            filters['is_active'] = self.request.query_params.get('is_active')
        return self.variant_service.build_queryset(filters)


class CategoryViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all().prefetch_related('products', 'children')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, CATEGORIES_PERMS]
    audit_module = 'categories'
    # Categories are a small tree; paginating hid rows from the FE client-side search.
    pagination_class = None
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

    def get_permissions(self):
        if getattr(self, 'action', None) == 'destroy':
            from approvals.permissions import is_maker_checker_enabled

            if is_maker_checker_enabled():
                return [IsAuthenticated(), HasPermission('categories', 'update')]
        return [IsAuthenticated(), CATEGORIES_PERMS()]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        from approvals.category_integration import queue_category_deactivate
        from approvals.permissions import is_maker_checker_enabled
        from approvals.serializers import PendingChangeSerializer

        validated = dict(serializer.validated_data)
        pending = None
        if (
            is_maker_checker_enabled()
            and validated.get('is_active') is False
            and instance.is_active
            and 'is_active' in serializer.initial_data
        ):
            try:
                pending = queue_category_deactivate(request, instance)
            except ValidationError as exc:
                from rest_framework.exceptions import ValidationError as DRFValidationError

                if hasattr(exc, 'message_dict'):
                    raise DRFValidationError(exc.message_dict)
                raise DRFValidationError(str(exc))
            serializer.validated_data.pop('is_active', None)

        if serializer.validated_data:
            self.perform_update(serializer)
        elif pending is None:
            return Response(serializer.data)

        instance.refresh_from_db()
        data = self.get_serializer(instance).data
        if pending:
            return Response(
                {
                    'message': 'Change submitted for approval, not yet active.',
                    'pending_change': PendingChangeSerializer(pending).data,
                    'category': data,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        from approvals.category_integration import queue_category_delete
        from approvals.permissions import is_maker_checker_enabled
        from approvals.serializers import PendingChangeSerializer

        if is_maker_checker_enabled():
            instance = self.get_object()
            try:
                pending = queue_category_delete(request, instance)
            except ValidationError as exc:
                from rest_framework.exceptions import ValidationError as DRFValidationError

                if hasattr(exc, 'message_dict'):
                    raise DRFValidationError(exc.message_dict)
                raise DRFValidationError(str(exc))
            return Response(
                {
                    'message': 'Change submitted for approval, not yet active.',
                    'pending_change': PendingChangeSerializer(pending).data,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in a category"""
        category = self.get_object()
        products = self.category_service.get_category_products(category.id, active_only=True)
        serializer = ProductListSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)


class ProductViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, PRODUCTS_PERMS]
    audit_module = 'products'
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sku', 'barcode', 'description', 'supplier__name', 'category__name']
    ordering_fields = ['name', 'price', 'cost', 'created_at', 'stock_quantity', 'updated_at']
    ordering = ['name']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.product_service = ProductService()

    def get_permissions(self):
        """With maker-checker, DELETE queues a proposal — ``update`` is enough for makers."""
        if getattr(self, 'action', None) == 'destroy':
            from approvals.permissions import is_maker_checker_enabled

            if is_maker_checker_enabled():
                return [IsAuthenticated(), HasPermission('products', 'update')]
        return [IsAuthenticated(), PRODUCTS_PERMS()]

    @staticmethod
    def _feature_disabled_response(feature_label: str):
        return Response(
            {'error': f'{feature_label} is disabled in store settings.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters, ignoring "undefined" values from frontend
        for param in ['is_active', 'category', 'subcategory', 'low_stock', 
                     'out_of_stock', 'track_stock', 'supplier', 'needs_restock']:
            if param in query_params:
                value = query_params.get(param)
                # Skip "undefined", "null", empty strings, and None values
                if value and value.lower() not in ['undefined', 'null', '']:
                    filters[param] = value
        
        return self.product_service.build_queryset(filters)
    
    def perform_create(self, serializer):
        """Create product - thin view, business logic in service"""
        try:
            # Let serializer create the product (handles ManyToMany fields)
            product = serializer.save()
            from accounts.models import AuditLog
            from utils.audit_events import log_product_write

            log_product_write(
                self.request, product, before=None, action=AuditLog.ACTION_CREATE
            )
            
            # Variants only when the module feature is on
            if is_product_variants_enabled() and product.has_variants:
                sizes = product.available_sizes.all()
                colors = product.available_colors.all()
                if sizes.exists() or colors.exists():
                    self.product_service.variant_service.create_variants_for_product(
                        product,
                        sizes=[s.id for s in sizes] if sizes.exists() else None,
                        colors=[c.id for c in colors] if colors.exists() else None
                    )
            elif product.has_variants:
                product.has_variants = False
                product.available_sizes.clear()
                product.available_colors.clear()
                product.save(update_fields=['has_variants'])
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating product: {e}", exc_info=True)
            # Re-raise to let DRF handle it properly
            raise
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        from approvals.integration import queue_product_sensitive_update, split_product_payload
        from approvals.serializers import PendingChangeSerializer

        from approvals.permissions import is_maker_checker_enabled

        validated = dict(serializer.validated_data)
        submitted_keys = set(serializer.initial_data.keys())
        sensitive, _immediate = split_product_payload(
            validated,
            submitted_keys=submitted_keys,
        )
        try:
            pending = queue_product_sensitive_update(request, instance, sensitive)
        except ValidationError as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            if hasattr(exc, 'message_dict'):
                raise DRFValidationError(exc.message_dict)
            raise DRFValidationError(str(exc))

        if pending is not None:
            for key in sensitive:
                serializer.validated_data.pop(key, None)
        elif is_maker_checker_enabled() and sensitive:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(
                {'reason': 'A reason is required for price, stock, or status changes.'}
            )

        if serializer.validated_data:
            self.perform_update(serializer)
        elif pending is None:
            return Response(serializer.data)

        instance.refresh_from_db()
        data = self.get_serializer(instance).data
        if pending:
            return Response(
                {
                    'message': 'Change submitted for approval, not yet active.',
                    'pending_change': PendingChangeSerializer(pending).data,
                    'product': data,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(data)

    def perform_update(self, serializer):
        """Update product - serializer handles update, service handles variant changes"""
        from accounts.models import AuditLog
        from utils.audit_events import log_product_write

        if not serializer.validated_data:
            return serializer.instance

        before = None
        if serializer.instance and serializer.instance.pk:
            before = self.get_queryset().get(pk=serializer.instance.pk)
        product = serializer.save()
        log_product_write(
            self.request, product, before=before, action=AuditLog.ACTION_UPDATE
        )
        
        # Handle variant updates if variant settings changed
        # Check if variants need to be recreated
        sizes = product.available_sizes.all()
        colors = product.available_colors.all()
        
        if is_product_variants_enabled() and product.has_variants and (sizes.exists() or colors.exists()):
            # Delete existing variants and recreate
            ProductVariant.objects.filter(product=product).delete()
            self.product_service.variant_service.create_variants_for_product(
                product,
                sizes=[s.id for s in sizes] if sizes.exists() else None,
                colors=[c.id for c in colors] if colors.exists() else None
            )
        elif not product.has_variants or not is_product_variants_enabled():
            # Feature off or flag cleared — sell as a simple product
            if product.has_variants:
                product.has_variants = False
                product.available_sizes.clear()
                product.available_colors.clear()
                product.save(update_fields=['has_variants'])
            ProductVariant.objects.filter(product=product).delete()

    def destroy(self, request, *args, **kwargs):
        from approvals.integration import queue_product_delete
        from approvals.permissions import is_maker_checker_enabled
        from approvals.serializers import PendingChangeSerializer

        if is_maker_checker_enabled():
            instance = self.get_object()
            try:
                pending = queue_product_delete(request, instance)
            except ValidationError as exc:
                from rest_framework.exceptions import ValidationError as DRFValidationError

                if hasattr(exc, 'message_dict'):
                    raise DRFValidationError(exc.message_dict)
                raise DRFValidationError(str(exc))
            return Response(
                {
                    'message': 'Change submitted for approval, not yet active.',
                    'pending_change': PendingChangeSerializer(pending).data,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Quick search endpoint for POS"""
        try:
            query = request.query_params.get('q', '').strip()
            if not query:
                return Response([])
            
            # Safely parse limit parameter with validation
            limit_param = request.query_params.get('limit', '20')
            try:
                limit = int(limit_param)
                # Validate limit is reasonable (between 1 and 1000)
                if limit < 1:
                    limit = 20
                elif limit > 1000:
                    limit = 1000
            except (ValueError, TypeError):
                limit = 20
            
            products = self.product_service.search_products(query, limit)
            serializer = ProductSearchSerializer(products, many=True)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in product search: {e}", exc_info=True)
            return Response(
                {'error': 'An error occurred while searching products'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
        if not products_bulk_operations_enabled():
            return self._feature_disabled_response('Bulk operations')
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
        if not products_bulk_operations_enabled():
            return self._feature_disabled_response('Bulk operations')
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
        if not products_bulk_operations_enabled():
            return self._feature_disabled_response('Bulk operations')
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
        if not products_bulk_operations_enabled():
            return self._feature_disabled_response('Bulk operations')
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
        if not products_csv_import_export_enabled():
            return self._feature_disabled_response('CSV import/export')
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
        if not products_csv_import_export_enabled():
            return self._feature_disabled_response('CSV import/export')
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        try:
            results = self.product_service.import_products_from_csv(file, user=request.user)
            
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
