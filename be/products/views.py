from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q, F, Sum, Count, Avg
from django.db import transaction
from django.http import HttpResponse
from .models import Category, Product, Size, Color, ProductVariant
from .serializers import (
    CategorySerializer, CategoryListSerializer,
    ProductSerializer, ProductListSerializer, ProductSearchSerializer,
    BulkProductUpdateSerializer, ProductStatisticsSerializer,
    SizeSerializer, ColorSerializer, ProductVariantSerializer
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
    
    def get_queryset(self):
        queryset = Size.objects.all()
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class ColorViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product colors"""
    queryset = Color.objects.all()
    serializer_class = ColorSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = Color.objects.all()
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class ProductVariantViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product variants"""
    queryset = ProductVariant.objects.select_related('product', 'size', 'color').all()
    serializer_class = ProductVariantSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['sku', 'barcode', 'product__name']
    ordering_fields = ['product', 'size', 'color', 'sku']
    ordering = ['product', 'size', 'color']
    
    def get_queryset(self):
        queryset = ProductVariant.objects.select_related('product', 'size', 'color').all()
        product_id = self.request.query_params.get('product', None)
        is_active = self.request.query_params.get('is_active', None)
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().prefetch_related('products', 'children')
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = Category.objects.all().prefetch_related('products', 'children')
        is_active = self.request.query_params.get('is_active', None)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return CategoryListSerializer
        return CategorySerializer

    def get_queryset(self):
        queryset = Category.objects.all()
        is_active = self.request.query_params.get('is_active', None)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in a category"""
        category = self.get_object()
        products = category.products.filter(is_active=True)
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

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.select_related('category', 'subcategory').prefetch_related(
            'available_sizes', 'available_colors', 'variants'
        )
        is_active = self.request.query_params.get('is_active', None)
        category = self.request.query_params.get('category', None)
        low_stock = self.request.query_params.get('low_stock', None)
        out_of_stock = self.request.query_params.get('out_of_stock', None)
        track_stock = self.request.query_params.get('track_stock', None)
        supplier = self.request.query_params.get('supplier', None)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if category:
            queryset = queryset.filter(category_id=category)
        
        subcategory = self.request.query_params.get('subcategory', None)
        if subcategory:
            queryset = queryset.filter(subcategory_id=subcategory)
        
        if low_stock is not None and low_stock.lower() == 'true':
            queryset = queryset.filter(
                stock_quantity__lte=F('low_stock_threshold'),
                track_stock=True
            )
        
        if out_of_stock is not None and out_of_stock.lower() == 'true':
            queryset = queryset.filter(stock_quantity=0, track_stock=True)
        
        if track_stock is not None:
            queryset = queryset.filter(track_stock=track_stock.lower() == 'true')
        
        if supplier:
            queryset = queryset.filter(supplier__icontains=supplier)
        
        return queryset

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Quick search endpoint for POS"""
        query = request.query_params.get('q', '').strip()
        limit = int(request.query_params.get('limit', 20))
        
        if not query:
            return Response([])
        
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(barcode__icontains=query),
            is_active=True
        )[:limit]
        
        serializer = ProductSearchSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get products with low stock"""
        products = Product.objects.filter(
            stock_quantity__lte=F('low_stock_threshold'),
            is_active=True,
            track_stock=True
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        """Get products that are out of stock"""
        products = Product.objects.filter(
            stock_quantity=0,
            is_active=True,
            track_stock=True
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Bulk update products"""
        serializer = BulkProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_ids = serializer.validated_data['product_ids']
        update_data = serializer.validated_data['update_data']
        
        updated_count = Product.objects.filter(id__in=product_ids).update(**update_data)
        
        return Response({
            'message': f'{updated_count} products updated successfully',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete products"""
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids:
            return Response(
                {'error': 'No product IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deleted_count = Product.objects.filter(id__in=product_ids).delete()[0]
        
        return Response({
            'message': f'{deleted_count} products deleted successfully',
            'deleted_count': deleted_count
        })

    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Bulk activate products"""
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids:
            return Response(
                {'error': 'No product IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_count = Product.objects.filter(id__in=product_ids).update(is_active=True)
        
        return Response({
            'message': f'{updated_count} products activated successfully',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate products"""
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids:
            return Response(
                {'error': 'No product IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_count = Product.objects.filter(id__in=product_ids).update(is_active=False)
        
        return Response({
            'message': f'{updated_count} products deactivated successfully',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get product statistics"""
        stats = {
            'total_products': Product.objects.count(),
            'active_products': Product.objects.filter(is_active=True).count(),
            'low_stock_products': Product.objects.filter(
                stock_quantity__lte=F('low_stock_threshold'),
                track_stock=True,
                is_active=True
            ).count(),
            'out_of_stock_products': Product.objects.filter(
                stock_quantity=0,
                track_stock=True,
                is_active=True
            ).count(),
        }
        
        # Calculate total inventory value
        inventory_value = Product.objects.filter(track_stock=True).aggregate(
            total=Sum(F('stock_quantity') * F('cost'))
        )['total'] or 0
        
        # Calculate total products value (at selling price)
        products_value = Product.objects.filter(track_stock=True).aggregate(
            total=Sum(F('stock_quantity') * F('price'))
        )['total'] or 0
        
        stats['total_inventory_value'] = float(inventory_value)
        stats['total_products_value'] = float(products_value)
        
        serializer = ProductStatisticsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export products to CSV with all fields matching the template format"""
        products = self.get_queryset()
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
        
        # Write BOM for Excel compatibility
        response.write('\ufeff')
        
        writer = csv.writer(response)
        # Headers matching the template format
        writer.writerow([
            'name',
            'sku',
            'barcode',
            'category',
            'subcategory',
            'price',
            'cost',
            'stock_quantity',
            'low_stock_threshold',
            'reorder_quantity',
            'unit',
            'description',
            'supplier',
            'supplier_contact',
            'tax_rate',
            'is_taxable',
            'track_stock',
            'is_active',
            'has_variants',
            'available_sizes',
            'available_colors'
        ])
        
        for product in products:
            # Get sizes and colors as comma-separated values
            sizes = ','.join([size.name for size in product.available_sizes.all()])
            colors = ','.join([color.name for color in product.available_colors.all()])
            
            writer.writerow([
                product.name or '',
                product.sku or '',
                product.barcode or '',
                product.category.name if product.category else '',
                product.subcategory.name if product.subcategory else '',
                str(product.price) if product.price else '0.00',
                str(product.cost) if product.cost else '0.00',
                str(product.stock_quantity) if product.stock_quantity else '0',
                str(product.low_stock_threshold) if product.low_stock_threshold else '10',
                str(product.reorder_quantity) if product.reorder_quantity else '50',
                product.unit or 'piece',
                product.description or '',
                product.supplier or '',
                product.supplier_contact or '',
                str(product.tax_rate) if product.tax_rate else '0',
                'true' if product.is_taxable else 'false',
                'true' if product.track_stock else 'false',
                'true' if product.is_active else 'false',
                'true' if product.has_variants else 'false',
                sizes,
                colors
            ])
        
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
            # Try to decode with UTF-8, fallback to latin-1
            try:
                decoded_file = file.read().decode('utf-8-sig')  # Handle BOM
            except UnicodeDecodeError:
                file.seek(0)
                decoded_file = file.read().decode('latin-1')
            
            # Skip comment lines (lines starting with #)
            lines = [line for line in decoded_file.splitlines() if line.strip() and not line.strip().startswith('#')]
            
            if not lines:
                return Response(
                    {'error': 'CSV file is empty or contains only comments'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            csv_reader = csv.DictReader(lines)
            
            created_count = 0
            updated_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Support both template format (lowercase) and old format (title case)
                    sku = row.get('sku', row.get('SKU', '')).strip()
                    if not sku:
                        errors.append(f"Row {row_num}: SKU is required")
                        continue
                    
                    # Get values with fallback to old format
                    name = row.get('name', row.get('Name', '')).strip()
                    if not name:
                        errors.append(f"Row {row_num}: Name is required")
                        continue
                    
                    # Parse boolean fields
                    def parse_bool(value, default=False):
                        if isinstance(value, bool):
                            return value
                        if isinstance(value, str):
                            return value.strip().lower() in ('true', 'yes', '1', 'y')
                        return default
                    
                    # Parse numeric fields
                    def parse_decimal(value, default=0):
                        try:
                            return float(value) if value else default
                        except (ValueError, TypeError):
                            return default
                    
                    def parse_int(value, default=0):
                        try:
                            return int(float(value)) if value else default
                        except (ValueError, TypeError):
                            return default
                    
                    # Get all fields
                    price = parse_decimal(row.get('price', row.get('Price', 0)))
                    cost = parse_decimal(row.get('cost', row.get('Cost', 0)))
                    stock_quantity = parse_int(row.get('stock_quantity', row.get('Stock Quantity', 0)))
                    low_stock_threshold = parse_int(row.get('low_stock_threshold', row.get('Low Stock Threshold', 10)))
                    reorder_quantity = parse_int(row.get('reorder_quantity', row.get('Reorder Quantity', 50)))
                    tax_rate = parse_decimal(row.get('tax_rate', row.get('Tax Rate', 0)))
                    
                    product, created = Product.objects.update_or_create(
                        sku=sku,
                        defaults={
                            'name': name,
                            'barcode': row.get('barcode', row.get('Barcode', '')).strip() or None,
                            'price': price,
                            'cost': cost,
                            'stock_quantity': stock_quantity,
                            'low_stock_threshold': low_stock_threshold,
                            'reorder_quantity': reorder_quantity,
                            'unit': row.get('unit', row.get('Unit', 'piece')).strip() or 'piece',
                            'description': row.get('description', row.get('Description', '')).strip(),
                            'supplier': row.get('supplier', row.get('Supplier', '')).strip(),
                            'supplier_contact': row.get('supplier_contact', row.get('Supplier Contact', '')).strip(),
                            'tax_rate': tax_rate,
                            'is_taxable': parse_bool(row.get('is_taxable', row.get('Is Taxable', True))),
                            'track_stock': parse_bool(row.get('track_stock', row.get('Track Stock', True))),
                            'is_active': parse_bool(row.get('is_active', row.get('Is Active', True))),
                            'has_variants': parse_bool(row.get('has_variants', row.get('Has Variants', False))),
                        }
                    )
                    
                    # Handle category
                    category_name = row.get('category', row.get('Category', '')).strip()
                    if category_name:
                        category, _ = Category.objects.get_or_create(
                            name=category_name,
                            defaults={'is_active': True}
                        )
                        product.category = category
                    
                    # Handle subcategory
                    subcategory_name = row.get('subcategory', row.get('Subcategory', '')).strip()
                    if subcategory_name:
                        # Subcategory must be a child of the main category
                        parent_category = product.category if product.category else None
                        if parent_category:
                            subcategory, _ = Category.objects.get_or_create(
                                name=subcategory_name,
                                parent=parent_category,
                                defaults={'is_active': True}
                            )
                            product.subcategory = subcategory
                    
                    # Handle sizes and colors (comma-separated)
                    sizes_str = row.get('available_sizes', row.get('Available Sizes', '')).strip()
                    if sizes_str:
                        size_names = [s.strip() for s in sizes_str.split(',') if s.strip()]
                        sizes = []
                        for size_name in size_names:
                            size, _ = Size.objects.get_or_create(
                                name=size_name,
                                defaults={'is_active': True}
                            )
                            sizes.append(size)
                        product.available_sizes.set(sizes)
                    
                    colors_str = row.get('available_colors', row.get('Available Colors', '')).strip()
                    if colors_str:
                        color_names = [c.strip() for c in colors_str.split(',') if c.strip()]
                        colors = []
                        for color_name in color_names:
                            color, _ = Color.objects.get_or_create(
                                name=color_name,
                                defaults={'is_active': True}
                            )
                            colors.append(color)
                        product.available_colors.set(colors)
                    
                    product.save()
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            message = f'Import completed: {created_count} created, {updated_count} updated'
            if errors:
                message += f'. {len(errors)} errors occurred.'
            
            return Response({
                'message': message,
                'created_count': created_count,
                'updated_count': updated_count,
                'errors': errors[:10]  # Limit errors to first 10
            })
            
        except Exception as e:
            return Response(
                {'error': f'Import failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
