"""
Product service layer - handles all product business logic
Moved from be/services/products_service.py to be/products/services.py
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg, F, QuerySet
from django.core.exceptions import ValidationError
from .models import Product, Category, Size, Color, ProductVariant
from suppliers.models import Supplier
from services.base import BaseService, QueryService


class CategoryService(BaseService):
    """Service for category operations"""
    
    def __init__(self):
        super().__init__(Category)
    
    def get_active_categories(self, parent_id: Optional[int] = None) -> List[Category]:
        """Get active categories, optionally filtered by parent"""
        queryset = self.model.objects.filter(is_active=True)
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        else:
            queryset = queryset.filter(parent__isnull=True)
        return list(queryset)
    
    def get_category_with_children(self, category_id: int) -> Category:
        """Get category with all children"""
        return self.model.objects.prefetch_related('children').get(pk=category_id)
    
    def validate_parent_child_relationship(self, category_id: int, 
                                          parent_id: Optional[int]) -> bool:
        """Validate that parent-child relationship is valid"""
        if not parent_id:
            return True
        
        try:
            parent = self.model.objects.get(pk=parent_id)
            if parent.parent_id:  # Parent cannot be a subcategory
                raise ValidationError("Cannot set a subcategory as parent")
            return True
        except self.model.DoesNotExist:
            raise ValidationError(f"Parent category {parent_id} does not exist")
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for category listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
                - parent: int (parent category ID)
        
        Returns:
            QuerySet of categories
        """
        queryset = self.model.objects.all().prefetch_related('products', 'children')
        
        if not filters:
            return queryset
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        parent = filters.get('parent')
        if parent is not None:
            try:
                parent_id = int(parent)
                queryset = queryset.filter(parent_id=parent_id)
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        return queryset
    
    def get_category_products(self, category_id: int, active_only: bool = True) -> QuerySet:
        """Get all products in a category"""
        category = self.get(category_id)
        queryset = category.products.all()
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset


class SizeService(BaseService):
    """Service for size operations"""
    
    def __init__(self):
        super().__init__(Size)
    
    def get_active_sizes(self) -> List[Size]:
        """Get all active sizes ordered by display order"""
        return list(self.model.objects.filter(is_active=True).order_by('display_order', 'name'))
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for size listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
        
        Returns:
            QuerySet of sizes
        """
        queryset = self.model.objects.all()
        
        if not filters:
            return queryset
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        return queryset.order_by('display_order', 'name')


class ColorService(BaseService):
    """Service for color operations"""
    
    def __init__(self):
        super().__init__(Color)
    
    def get_active_colors(self) -> List[Color]:
        """Get all active colors"""
        return list(self.model.objects.filter(is_active=True).order_by('name'))
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for color listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
        
        Returns:
            QuerySet of colors
        """
        queryset = self.model.objects.all()
        
        if not filters:
            return queryset
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        return queryset.order_by('name')


class ProductVariantService(BaseService):
    """Service for product variant operations"""
    
    def __init__(self):
        super().__init__(ProductVariant)
    
    def create_variants_for_product(self, product: Product, 
                                   sizes: Optional[List[int]] = None,
                                   colors: Optional[List[int]] = None) -> List[ProductVariant]:
        """Create all variants for a product based on sizes and colors"""
        if not product.has_variants:
            return []
        
        variants = []
        size_objs = Size.objects.filter(id__in=sizes) if sizes else []
        color_objs = Color.objects.filter(id__in=colors) if colors else []
        
        # Create variants for each size/color combination
        if size_objs and color_objs:
            for size in size_objs:
                for color in color_objs:
                    variant = self._create_variant(product, size, color)
                    variants.append(variant)
        elif size_objs:
            for size in size_objs:
                variant = self._create_variant(product, size, None)
                variants.append(variant)
        elif color_objs:
            for color in color_objs:
                variant = self._create_variant(product, None, color)
                variants.append(variant)
        
        return variants
    
    def _create_variant(self, product: Product, size: Optional[Size], 
                       color: Optional[Color]) -> ProductVariant:
        """Create a single variant"""
        sku_parts = [product.sku]
        if size:
            sku_parts.append(size.code)
        if color:
            sku_parts.append(color.name[:3].upper())
        
        variant_sku = '-'.join(sku_parts)
        
        # Calculate variant price (can be customized)
        variant_price = product.price
        variant_cost = product.cost
        
        return ProductVariant.objects.create(
            product=product,
            size=size,
            color=color,
            sku=variant_sku,
            price=variant_price,
            cost=variant_cost,
            stock_quantity=0,
            low_stock_threshold=product.low_stock_threshold,
            is_active=True
        )
    
    def get_variants_for_product(self, product_id: int) -> List[ProductVariant]:
        """Get all variants for a product"""
        return list(self.model.objects.filter(product_id=product_id).select_related('size', 'color'))
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for variant listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - product: int (product ID)
                - is_active: bool or str ('true'/'false')
        
        Returns:
            QuerySet of variants
        """
        queryset = self.model.objects.select_related('product', 'size', 'color').all()
        
        if not filters:
            return queryset
        
        product_id = filters.get('product')
        if product_id:
            try:
                queryset = queryset.filter(product_id=int(product_id))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        return queryset


class ProductService(BaseService):
    """Service for product operations"""
    
    def __init__(self):
        super().__init__(Product)
        self.variant_service = ProductVariantService()
        self.category_service = CategoryService()
    
    def search_products(self, query: str, limit: int = 50) -> List[Product]:
        """Search products by name, SKU, or barcode"""
        if not query or not query.strip():
            return []
        
        queryset = self.model.objects.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(barcode__icontains=query)
        ).filter(is_active=True)[:limit]
        
        return list(queryset)
    
    def get_low_stock_products(self) -> List[Product]:
        """Get products with stock below threshold"""
        return list(self.model.objects.filter(
            track_stock=True,
            is_active=True,
            stock_quantity__lt=F('low_stock_threshold')
        ).exclude(stock_quantity=0))
    
    def get_out_of_stock_products(self) -> List[Product]:
        """Get products that are out of stock"""
        return list(self.model.objects.filter(
            track_stock=True,
            is_active=True,
            stock_quantity=0
        ))
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for product listing.
        Moves query building logic from views to service layer.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
                - category: int (category ID)
                - subcategory: int (subcategory ID)
                - low_stock: bool or str ('true'/'false')
                - out_of_stock: bool or str ('true'/'false')
                - track_stock: bool or str ('true'/'false')
                - supplier: int or str (supplier ID or name for legacy search)
        
        Returns:
            QuerySet of products with proper select_related/prefetch_related
        """
        queryset = self.model.objects.select_related(
            'category', 'subcategory', 'supplier'
        ).prefetch_related(
            'available_sizes', 'available_colors', 'variants'
        )
        
        if not filters:
            return queryset
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        category = filters.get('category')
        if category:
            try:
                queryset = queryset.filter(category_id=int(category))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        subcategory = filters.get('subcategory')
        if subcategory:
            try:
                queryset = queryset.filter(subcategory_id=int(subcategory))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        low_stock = filters.get('low_stock')
        if low_stock is not None:
            if isinstance(low_stock, str):
                low_stock = low_stock.lower() == 'true'
            if low_stock:
                queryset = queryset.filter(
                    stock_quantity__lte=F('low_stock_threshold'),
                    track_stock=True
                )
        
        out_of_stock = filters.get('out_of_stock')
        if out_of_stock is not None:
            if isinstance(out_of_stock, str):
                out_of_stock = out_of_stock.lower() == 'true'
            if out_of_stock:
                queryset = queryset.filter(stock_quantity=0, track_stock=True)
        
        track_stock = filters.get('track_stock')
        if track_stock is not None:
            if isinstance(track_stock, str):
                track_stock = track_stock.lower() == 'true'
            queryset = queryset.filter(track_stock=track_stock)
        
        supplier = filters.get('supplier')
        if supplier:
            try:
                # Try to find supplier by ID first
                supplier_obj = Supplier.objects.get(id=int(supplier))
                queryset = queryset.filter(supplier=supplier_obj)
            except (Supplier.DoesNotExist, ValueError, TypeError):
                # Fallback to legacy supplier name search
                queryset = queryset.filter(supplier_name__icontains=str(supplier))
        
        return queryset
    
    @transaction.atomic
    def create_product(self, data: Dict[str, Any], 
                      sizes: Optional[List[int]] = None,
                      colors: Optional[List[int]] = None) -> Product:
        """Create a product with optional variants"""
        # Extract variant-related data (handle both object lists and ID lists)
        has_variants = data.pop('has_variants', False)
        available_sizes_data = data.pop('available_sizes', sizes or [])
        available_colors_data = data.pop('available_colors', colors or [])
        
        # Convert to ID lists if objects provided
        if available_sizes_data and isinstance(available_sizes_data[0], Size):
            available_sizes = [s.id for s in available_sizes_data]
        else:
            available_sizes = available_sizes_data or sizes or []
        
        if available_colors_data and isinstance(available_colors_data[0], Color):
            available_colors = [c.id for c in available_colors_data]
        else:
            available_colors = available_colors_data or colors or []
        
        # Validate supplier if provided
        supplier_id = data.get('supplier')
        if supplier_id:
            try:
                Supplier.objects.get(pk=supplier_id)
            except Supplier.DoesNotExist:
                raise ValidationError(f"Supplier {supplier_id} does not exist")
        
        # Validate category (handle both ID and object)
        category = data.get('category')
        if category:
            if isinstance(category, Category):
                category_id = category.id
            elif hasattr(category, 'id'):
                category_id = category.id
            else:
                category_id = category
            
            try:
                category_obj = Category.objects.get(pk=category_id)
                data['category'] = category_obj
            except (Category.DoesNotExist, ValueError, TypeError):
                raise ValidationError(f"Category {category_id} does not exist")
        
        # Validate SKU uniqueness
        sku = data.get('sku')
        if sku and self.model.objects.filter(sku=sku).exists():
            raise ValidationError(f"Product with SKU {sku} already exists")
        
        # Validate barcode uniqueness if provided
        barcode = data.get('barcode')
        if barcode and self.model.objects.filter(barcode=barcode).exists():
            raise ValidationError(f"Product with barcode {barcode} already exists")
        
        # Set has_variants in data
        data['has_variants'] = has_variants
        
        # Create product
        product = self.model.objects.create(**data)
        
        # Set ManyToMany fields if provided
        if available_sizes:
            product.available_sizes.set(Size.objects.filter(id__in=available_sizes))
        if available_colors:
            product.available_colors.set(Color.objects.filter(id__in=available_colors))
        
        # Create variants if needed
        if has_variants and (available_sizes or available_colors):
            self.variant_service.create_variants_for_product(
                product, available_sizes, available_colors
            )
        
        return product
    
    @transaction.atomic
    def update_product(self, product: Product, data: Dict[str, Any],
                      sizes: Optional[List[int]] = None,
                      colors: Optional[List[int]] = None) -> Product:
        """Update a product and handle variant changes"""
        # Handle variant updates
        has_variants = data.pop('has_variants', product.has_variants)
        available_sizes = data.pop('available_sizes', sizes)
        available_colors = data.pop('available_colors', colors)
        
        # Update product fields
        for key, value in data.items():
            setattr(product, key, value)
        
        product.save()
        
        # Update variants if variant settings changed
        if has_variants != product.has_variants or available_sizes or available_colors:
            # Delete existing variants
            ProductVariant.objects.filter(product=product).delete()
            
            # Create new variants
            if has_variants and (available_sizes or available_colors):
                self.variant_service.create_variants_for_product(
                    product, available_sizes, available_colors
                )
        
        return product
    
    def bulk_update_products(self, product_ids: List[int], 
                            update_data: Dict[str, Any]) -> int:
        """Bulk update multiple products"""
        products = self.model.objects.filter(id__in=product_ids)
        updated = 0
        
        for product in products:
            for key, value in update_data.items():
                setattr(product, key, value)
            product.save()
            updated += 1
        
        return updated
    
    def bulk_delete_products(self, product_ids: List[int]) -> int:
        """Bulk delete multiple products"""
        products = self.model.objects.filter(id__in=product_ids)
        count = products.count()
        products.delete()
        return count
    
    def bulk_activate_products(self, product_ids: List[int]) -> int:
        """Bulk activate products"""
        return self.model.objects.filter(id__in=product_ids).update(is_active=True)
    
    def bulk_deactivate_products(self, product_ids: List[int]) -> int:
        """Bulk deactivate products"""
        return self.model.objects.filter(id__in=product_ids).update(is_active=False)
    
    def get_product_statistics(self) -> Dict[str, Any]:
        """Get comprehensive product statistics"""
        try:
            queryset = self.model.objects.all()
            
            # Calculate inventory value (stock quantity * cost)
            inventory_agg = queryset.aggregate(
                total=Sum(F('stock_quantity') * F('cost'))
            )
            total_inventory_value = inventory_agg['total']
            if total_inventory_value is None:
                total_inventory_value = Decimal('0')
            
            # Calculate total products value (stock quantity * price)
            products_agg = queryset.aggregate(
                total=Sum(F('stock_quantity') * F('price'))
            )
            total_products_value = products_agg['total']
            if total_products_value is None:
                total_products_value = Decimal('0')
            
            # Get low stock and out of stock counts
            low_stock_list = self.get_low_stock_products()
            out_of_stock_list = self.get_out_of_stock_products()
            
            stats = {
                'total_products': queryset.count(),
                'active_products': queryset.filter(is_active=True).count(),
                'low_stock_products': len(low_stock_list) if low_stock_list else 0,
                'out_of_stock_products': len(out_of_stock_list) if out_of_stock_list else 0,
                'total_inventory_value': float(total_inventory_value),
                'total_products_value': float(total_products_value),
            }
            
            return stats
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in get_product_statistics: {e}", exc_info=True)
            # Return safe defaults on error
            return {
                'total_products': 0,
                'active_products': 0,
                'low_stock_products': 0,
                'out_of_stock_products': 0,
                'total_inventory_value': 0.0,
                'total_products_value': 0.0,
            }
    
    def export_products_to_csv(self, queryset: Optional[QuerySet] = None) -> str:
        """Export products to CSV format"""
        import csv
        import io
        
        if queryset is None:
            queryset = self.model.objects.all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'SKU', 'Name', 'Barcode', 'Category', 'Subcategory',
            'Price', 'Cost', 'Stock Quantity', 'Low Stock Threshold',
            'Unit', 'Has Variants', 'Track Stock', 'Is Taxable', 'Is Active',
            'Description', 'Supplier'
        ])
        
        # Write data
        for product in queryset:
            writer.writerow([
                product.sku,
                product.name,
                product.barcode or '',
                product.category.name if product.category else '',
                product.subcategory.name if product.subcategory else '',
                product.price,
                product.cost,
                product.stock_quantity,
                product.low_stock_threshold,
                product.unit,
                product.has_variants,
                product.track_stock,
                product.is_taxable,
                product.is_active,
                product.description or '',
                product.supplier.name if product.supplier else '',
            ])
        
        return output.getvalue()
    
    @transaction.atomic
    def import_products_from_csv(self, csv_file) -> Dict[str, Any]:
        """Import products from CSV file - supports template and old format"""
        import csv
        import io
        
        results = {
            'created': 0,
            'updated': 0,
            'errors': []
        }
        
        try:
            # Try to decode with UTF-8, fallback to latin-1
            try:
                decoded_file = csv_file.read().decode('utf-8-sig')  # Handle BOM
            except UnicodeDecodeError:
                csv_file.seek(0)
                decoded_file = csv_file.read().decode('latin-1')
            
            # Skip comment lines (lines starting with #)
            lines = [line for line in decoded_file.splitlines() 
                    if line.strip() and not line.strip().startswith('#')]
            
            if not lines:
                results['errors'].append('CSV file is empty or contains only comments')
                return results
            
            reader = csv.DictReader(lines)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Support both template format (lowercase) and old format (title case)
                    sku = row.get('sku', row.get('SKU', '')).strip()
                    if not sku:
                        results['errors'].append(f"Row {row_num}: SKU is required")
                        continue
                    
                    name = row.get('name', row.get('Name', '')).strip()
                    if not name:
                        results['errors'].append(f"Row {row_num}: Name is required")
                        continue
                    
                    # Parse row data
                    parsed_data = self._parse_product_row(row)
                    
                    # Extract sizes and colors for variant creation
                    sizes_str = parsed_data.pop('_sizes_str', '')
                    colors_str = parsed_data.pop('_colors_str', '')
                    
                    # Handle sizes
                    sizes = []
                    if sizes_str:
                        size_names = [s.strip() for s in sizes_str.split(',') if s.strip()]
                        for size_name in size_names:
                            size, _ = Size.objects.get_or_create(
                                name=size_name,
                                defaults={'code': size_name[:3].upper(), 'is_active': True}
                            )
                            sizes.append(size.id)
                    
                    # Handle colors
                    colors = []
                    if colors_str:
                        color_names = [c.strip() for c in colors_str.split(',') if c.strip()]
                        for color_name in color_names:
                            color, _ = Color.objects.get_or_create(
                                name=color_name,
                                defaults={'is_active': True}
                            )
                            colors.append(color.id)
                    
                    # Check if product exists
                    product, created = self.model.objects.get_or_create(
                        sku=sku,
                        defaults=parsed_data
                    )
                    
                    if not created:
                        # Update existing product
                        for key, value in parsed_data.items():
                            setattr(product, key, value)
                        product.save()
                        results['updated'] += 1
                    else:
                        results['created'] += 1
                    
                    # Handle sizes and colors ManyToMany
                    if sizes:
                        product.available_sizes.set(Size.objects.filter(id__in=sizes))
                    if colors:
                        product.available_colors.set(Color.objects.filter(id__in=colors))
                    
                    # Create variants if needed
                    if product.has_variants and (sizes or colors):
                        self.variant_service.create_variants_for_product(
                            product, sizes, colors
                        )
                        
                except Exception as e:
                    results['errors'].append(f"Row {row_num}: {str(e)}")
        
        except Exception as e:
            results['errors'].append(f"CSV parsing error: {str(e)}")
        
        return results
    
    def _parse_product_row(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Parse a CSV row into product data - supports both template and old format"""
        from decimal import Decimal
        
        # Helper functions
        def parse_bool(value, default=False):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in ('true', '1', 'yes', 'y')
            return default
        
        def parse_decimal(value, default=0):
            try:
                return Decimal(str(value)) if value else Decimal(str(default))
            except:
                return Decimal(str(default))
        
        def parse_int(value, default=0):
            try:
                return int(float(value)) if value else default
            except:
                return default
        
        # Support both lowercase (template) and title case (old format)
        def get_field(key):
            return row.get(key.lower(), row.get(key, '')).strip()
        
        # Get category
        category = None
        category_name = get_field('Category')
        if category_name:
            category = Category.objects.filter(name=category_name).first()
            if not category:
                category = Category.objects.create(name=category_name, is_active=True)
        
        # Get subcategory
        subcategory = None
        subcategory_name = get_field('Subcategory')
        if subcategory_name and category:
            subcategory = Category.objects.filter(
                name=subcategory_name,
                parent=category
            ).first()
            if not subcategory:
                subcategory = Category.objects.create(
                    name=subcategory_name,
                    parent=category,
                    is_active=True
                )
        
        # Get supplier (try FK first, then legacy name)
        supplier = None
        supplier_name = get_field('Supplier')
        if supplier_name:
            supplier = Supplier.objects.filter(name=supplier_name).first()
        
        # Handle sizes and colors
        sizes_str = get_field('Available Sizes')
        colors_str = get_field('Available Colors')
        
        data = {
            'name': get_field('Name'),
            'barcode': get_field('Barcode') or None,
            'category': category,
            'subcategory': subcategory,
            'price': parse_decimal(get_field('Price')),
            'cost': parse_decimal(get_field('Cost')),
            'stock_quantity': parse_int(get_field('Stock Quantity')),
            'low_stock_threshold': parse_int(get_field('Low Stock Threshold'), 10),
            'reorder_quantity': parse_int(get_field('Reorder Quantity'), 50),
            'unit': get_field('Unit') or 'piece',
            'has_variants': parse_bool(get_field('Has Variants'), False),
            'track_stock': parse_bool(get_field('Track Stock'), True),
            'is_taxable': parse_bool(get_field('Is Taxable'), True),
            'is_active': parse_bool(get_field('Is Active'), True),
            'description': get_field('Description'),
            'supplier': supplier,
            'supplier_name': supplier_name if not supplier else '',  # Legacy support
            'supplier_contact': get_field('Supplier Contact'),  # Legacy support
            'tax_rate': parse_decimal(get_field('Tax Rate'), 0),
        }
        
        # Store sizes and colors strings for later processing
        data['_sizes_str'] = sizes_str
        data['_colors_str'] = colors_str
        
        return data
