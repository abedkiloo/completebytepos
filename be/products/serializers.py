from rest_framework import serializers
from .models import Category, Product, Size, Color, ProductVariant


class SizeSerializer(serializers.ModelSerializer):
    """Serializer for Size model"""
    class Meta:
        model = Size
        fields = ['id', 'name', 'code', 'display_order', 'is_active']
        read_only_fields = ['created_at', 'updated_at']


class ColorSerializer(serializers.ModelSerializer):
    """Serializer for Color model"""
    class Meta:
        model = Color
        fields = ['id', 'name', 'hex_code', 'is_active']
        read_only_fields = ['created_at', 'updated_at']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for ProductVariant model"""
    size_name = serializers.CharField(source='size.name', read_only=True)
    size_code = serializers.CharField(source='size.code', read_only=True)
    color_name = serializers.CharField(source='color.name', read_only=True)
    color_hex = serializers.CharField(source='color.hex_code', read_only=True)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    effective_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'size', 'size_name', 'size_code',
            'color', 'color_name', 'color_hex',
            'sku', 'barcode', 'price', 'cost',
            'effective_price', 'effective_cost',
            'stock_quantity', 'low_stock_threshold',
            'is_low_stock', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'sku']


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'parent', 'is_active',
            'product_count', 'children_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_product_count(self, obj):
        # Use prefetched products if available, otherwise query
        if hasattr(obj, 'products'):
            return obj.products.count()
        return obj.products.filter(is_active=True).count()
    
    def get_children_count(self, obj):
        # Use prefetched children if available, otherwise query
        if hasattr(obj, 'children'):
            return obj.children.count()
        return obj.children.all().count()


class CategoryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for category lists"""
    product_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'product_count', 'is_active']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    category_detail = serializers.SerializerMethodField()
    subcategory_name = serializers.SerializerMethodField()
    subcategory_detail = serializers.SerializerMethodField()
    available_sizes_detail = SizeSerializer(source='available_sizes', many=True, read_only=True)
    available_colors_detail = ColorSerializer(source='available_colors', many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    profit_margin = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    profit_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_value = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    needs_reorder = serializers.BooleanField(read_only=True)
    image_url = serializers.SerializerMethodField()
    supplier_name_display = serializers.SerializerMethodField()
    supplier_detail = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode', 
            'category', 'category_name', 'category_detail',
            'subcategory', 'subcategory_name', 'subcategory_detail',
            'has_variants', 'available_sizes', 'available_sizes_detail',
            'available_colors', 'available_colors_detail', 'variants',
            'price', 'cost', 'stock_quantity', 'low_stock_threshold', 'reorder_quantity',
            'unit', 'image', 'image_url', 'description', 
            'supplier', 'supplier_name', 'supplier_name_display', 'supplier_detail', 'supplier_contact',
            'tax_rate', 'is_taxable', 'track_stock', 'is_low_stock', 'needs_reorder',
            'profit_margin', 'profit_amount', 'total_value', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'sku']
    
    def to_internal_value(self, data):
        """Convert category/subcategory objects to IDs if needed"""
        # Make a copy to avoid mutating the original
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Handle category field
        if 'category' in data:
            category = data['category']
            if category is not None and category != '' and str(category).strip() != '':
                try:
                    # Check if it's a Category object
                    from .models import Category
                    if isinstance(category, Category):
                        data['category'] = category.id
                    elif hasattr(category, 'id'):  # It's an object with id attribute
                        data['category'] = category.id
                    elif isinstance(category, dict) and 'id' in category:  # It's a dict with id
                        data['category'] = int(category['id'])
                    elif isinstance(category, str) and category.isdigit():  # It's a string number
                        data['category'] = int(category)
                    elif isinstance(category, (int, float)):  # It's already a number
                        data['category'] = int(category)
                    else:
                        # Try to convert to int if possible
                        try:
                            data['category'] = int(category)
                        except (ValueError, TypeError):
                            data['category'] = None
                except (ValueError, TypeError, AttributeError):
                    data['category'] = None
            else:
                data['category'] = None
        
        # Handle subcategory field
        if 'subcategory' in data:
            subcategory = data['subcategory']
            if subcategory is not None and subcategory != '' and str(subcategory).strip() != '':
                try:
                    # Check if it's a Category object
                    from .models import Category
                    if isinstance(subcategory, Category):
                        data['subcategory'] = subcategory.id
                    elif hasattr(subcategory, 'id'):  # It's an object with id attribute
                        data['subcategory'] = subcategory.id
                    elif isinstance(subcategory, dict) and 'id' in subcategory:  # It's a dict with id
                        data['subcategory'] = int(subcategory['id'])
                    elif isinstance(subcategory, str) and subcategory.isdigit():  # It's a string number
                        data['subcategory'] = int(subcategory)
                    elif isinstance(subcategory, (int, float)):  # It's already a number
                        data['subcategory'] = int(subcategory)
                    else:
                        # Try to convert to int if possible
                        try:
                            data['subcategory'] = int(subcategory)
                        except (ValueError, TypeError):
                            data['subcategory'] = None
                except (ValueError, TypeError, AttributeError):
                    data['subcategory'] = None
            else:
                data['subcategory'] = None
        
        # Handle supplier field
        if 'supplier' in data:
            supplier = data['supplier']
            if supplier is not None and supplier != '':
                # Check if it's a Supplier object
                try:
                    from suppliers.models import Supplier
                    if isinstance(supplier, Supplier):
                        data['supplier'] = supplier.id
                    elif hasattr(supplier, 'id'):  # It's an object with id attribute
                        data['supplier'] = supplier.id
                    elif isinstance(supplier, dict) and 'id' in supplier:  # It's a dict with id
                        data['supplier'] = supplier['id']
                    elif isinstance(supplier, str) and supplier.isdigit():  # It's a string number
                        data['supplier'] = int(supplier)
                except ImportError:
                    # Suppliers app might not be available
                    pass
            else:
                data['supplier'] = None
        
        return super().to_internal_value(data)
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else None
    
    def get_category_detail(self, obj):
        if obj.category:
            return CategoryListSerializer(obj.category).data
        return None
    
    def get_subcategory_name(self, obj):
        return obj.subcategory.name if obj.subcategory else None
    
    def get_subcategory_detail(self, obj):
        if obj.subcategory:
            return CategoryListSerializer(obj.subcategory).data
        return None
    
    def get_supplier_name_display(self, obj):
        """Get supplier name - from FK if available, otherwise from legacy field"""
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name or ''
    
    def get_supplier_detail(self, obj):
        """Get full supplier details if supplier FK is set"""
        if obj.supplier:
            from suppliers.serializers import SupplierListSerializer
            return SupplierListSerializer(obj.supplier, context=self.context).data
        return None
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
    
    def validate_sku(self, value):
        """Validate SKU uniqueness"""
        if self.instance and self.instance.sku == value:
            return value
        if Product.objects.filter(sku=value).exists():
            raise serializers.ValidationError("A product with this SKU already exists.")
        return value
    
    def validate_barcode(self, value):
        """Validate barcode uniqueness"""
        if not value:
            return value
        if self.instance and self.instance.barcode == value:
            return value
        if Product.objects.filter(barcode=value).exists():
            raise serializers.ValidationError("A product with this barcode already exists.")
        return value
    
    def validate(self, data):
        """Validate product data"""
        if data.get('price', 0) < data.get('cost', 0):
            raise serializers.ValidationError({
                'price': 'Selling price should be greater than or equal to cost price.'
            })
        
        # Validate subcategory is a child of category
        category_id = data.get('category')
        subcategory_id = data.get('subcategory')
        
        # Handle case where category/subcategory might be objects instead of IDs
        from .models import Category
        if category_id and isinstance(category_id, Category):
            category_id = category_id.id
            data['category'] = category_id
        
        if subcategory_id and isinstance(subcategory_id, Category):
            subcategory_id = subcategory_id.id
            data['subcategory'] = subcategory_id
        
        # If updating, use instance values if not provided in data
        if self.instance:
            if category_id is None:
                category_id = self.instance.category_id
            if subcategory_id is None:
                subcategory_id = self.instance.subcategory_id
        
        # Auto-populate category from subcategory's parent if subcategory is provided but category doesn't match
        if subcategory_id:
            try:
                subcategory_id = int(subcategory_id) if subcategory_id else None
            except (ValueError, TypeError):
                subcategory_id = None
            
            if subcategory_id:
                try:
                    subcategory = Category.objects.get(id=subcategory_id)
                    # If subcategory has a parent, automatically set category to parent if not set or doesn't match
                    if subcategory.parent_id:
                        if not category_id or category_id != subcategory.parent_id:
                            # Auto-populate category from subcategory's parent
                            category_id = subcategory.parent_id
                            data['category'] = category_id
                except Category.DoesNotExist:
                    # Category doesn't exist, but this will be caught by field validation
                    pass
        
        # Validate that subcategory is a child of category (if both are set)
        if subcategory_id and category_id:
            # Ensure both are integers
            try:
                category_id = int(category_id) if category_id else None
                subcategory_id = int(subcategory_id) if subcategory_id else None
            except (ValueError, TypeError):
                pass
            
            if subcategory_id and category_id:
                # Fetch the actual Category objects to check parent relationship
                try:
                    subcategory = Category.objects.get(id=subcategory_id)
                    if subcategory.parent_id != category_id:
                        raise serializers.ValidationError({
                            'subcategory': 'Subcategory must be a child of the main category.'
                        })
                except Category.DoesNotExist:
                    # Category doesn't exist, but this will be caught by field validation
                    pass
        
        return data
    
    def create(self, validated_data):
        """Create product instance, handling ManyToMany fields separately"""
        # Extract ManyToMany fields
        available_sizes = validated_data.pop('available_sizes', [])
        available_colors = validated_data.pop('available_colors', [])
        
        # Handle category - ensure it's either a Category instance or None
        from .models import Category
        category_id = validated_data.pop('category', None)
        if category_id:
            if isinstance(category_id, Category):
                category = category_id
            else:
                try:
                    category_id = int(category_id)
                    category = Category.objects.get(id=category_id)
                except (ValueError, TypeError, Category.DoesNotExist):
                    category = None
        else:
            category = None
        
        # Handle subcategory - ensure it's either a Category instance or None
        subcategory_id = validated_data.pop('subcategory', None)
        if subcategory_id:
            if isinstance(subcategory_id, Category):
                subcategory = subcategory_id
            else:
                try:
                    subcategory_id = int(subcategory_id)
                    subcategory = Category.objects.get(id=subcategory_id)
                    # Auto-populate category from subcategory's parent if category not set
                    if not category and subcategory.parent:
                        category = subcategory.parent
                except (ValueError, TypeError, Category.DoesNotExist):
                    subcategory = None
        else:
            subcategory = None
        
        # Ensure supplier is ID, not object
        supplier_id = validated_data.pop('supplier', None)
        supplier = None
        if supplier_id:
            try:
                from suppliers.models import Supplier
                if isinstance(supplier_id, Supplier):
                    supplier = supplier_id
                elif hasattr(supplier_id, 'id'):
                    supplier = Supplier.objects.get(id=supplier_id.id)
                elif isinstance(supplier_id, str) and supplier_id.isdigit():
                    supplier = Supplier.objects.get(id=int(supplier_id))
                elif isinstance(supplier_id, (int, float)):
                    supplier = Supplier.objects.get(id=int(supplier_id))
            except (Supplier.DoesNotExist, ImportError, ValueError, TypeError):
                supplier = None
        
        # Create product instance with error handling
        try:
            product = Product.objects.create(
                category=category,
                subcategory=subcategory,
                supplier=supplier,
                **validated_data
            )
        except ValueError as e:
            # Convert model validation errors to serializer validation errors
            error_msg = str(e)
            # Check if it's a subcategory validation error
            if 'subcategory' in error_msg.lower():
                raise serializers.ValidationError({
                    'subcategory': error_msg
                })
            raise serializers.ValidationError(error_msg)
        
        # Set ManyToMany fields
        if available_sizes:
            product.available_sizes.set(available_sizes)
        if available_colors:
            product.available_colors.set(available_colors)
        
        return product
    
    def update(self, instance, validated_data):
        """Update product instance, handling ManyToMany fields separately"""
        # Extract ManyToMany fields
        available_sizes = validated_data.pop('available_sizes', None)
        available_colors = validated_data.pop('available_colors', None)
        
        # Handle category - ensure it's either a Category instance or None
        from .models import Category
        if 'category' in validated_data:
            category_id = validated_data.pop('category')
            if category_id:
                if isinstance(category_id, Category):
                    instance.category = category_id
                else:
                    try:
                        category_id = int(category_id)
                        instance.category = Category.objects.get(id=category_id)
                    except (ValueError, TypeError, Category.DoesNotExist):
                        instance.category = None
            else:
                instance.category = None
        
        # Handle subcategory - ensure it's either a Category instance or None
        if 'subcategory' in validated_data:
            subcategory_id = validated_data.pop('subcategory')
            if subcategory_id:
                if isinstance(subcategory_id, Category):
                    instance.subcategory = subcategory_id
                else:
                    try:
                        subcategory_id = int(subcategory_id)
                        subcategory = Category.objects.get(id=subcategory_id)
                        instance.subcategory = subcategory
                        # Auto-populate category from subcategory's parent if category not set
                        if not instance.category and subcategory.parent:
                            instance.category = subcategory.parent
                    except (ValueError, TypeError, Category.DoesNotExist):
                        instance.subcategory = None
            else:
                instance.subcategory = None
        
        # Handle supplier
        if 'supplier' in validated_data:
            supplier_id = validated_data.pop('supplier')
            if supplier_id:
                try:
                    from suppliers.models import Supplier
                    if isinstance(supplier_id, Supplier):
                        instance.supplier = supplier_id
                    elif hasattr(supplier_id, 'id'):
                        instance.supplier = Supplier.objects.get(id=supplier_id.id)
                    elif isinstance(supplier_id, str) and supplier_id.isdigit():
                        instance.supplier = Supplier.objects.get(id=int(supplier_id))
                    elif isinstance(supplier_id, (int, float)):
                        instance.supplier = Supplier.objects.get(id=int(supplier_id))
                    else:
                        instance.supplier = None
                except (Supplier.DoesNotExist, ImportError, ValueError, TypeError):
                    instance.supplier = None
            else:
                instance.supplier = None
        
        # Update regular fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Save with error handling
        try:
            instance.save()
        except ValueError as e:
            # Convert model validation errors to serializer validation errors
            error_msg = str(e)
            # Check if it's a subcategory validation error
            if 'subcategory' in error_msg.lower():
                raise serializers.ValidationError({
                    'subcategory': error_msg
                })
            raise serializers.ValidationError(error_msg)
        
        # Update ManyToMany fields if provided
        if available_sizes is not None:
            instance.available_sizes.set(available_sizes)
        if available_colors is not None:
            instance.available_colors.set(available_colors)
        
        return instance


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for product lists"""
    category_name = serializers.SerializerMethodField()
    subcategory_name = serializers.SerializerMethodField()
    has_variants = serializers.BooleanField(read_only=True)
    available_sizes_detail = SizeSerializer(source='available_sizes', many=True, read_only=True)
    available_colors_detail = ColorSerializer(source='available_colors', many=True, read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode', 'category_name', 'subcategory_name', 'has_variants',
            'available_sizes_detail', 'available_colors_detail',
            'price', 'cost', 'stock_quantity', 'unit',
            'is_low_stock', 'is_active', 'image_url'
        ]
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else None
    
    def get_subcategory_name(self, obj):
        return obj.subcategory.name if obj.subcategory else None
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ProductSearchSerializer(serializers.ModelSerializer):
    """Lightweight serializer for search results"""
    category_name = serializers.SerializerMethodField()
    has_variants = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'barcode', 'category_name', 'has_variants', 'price', 'stock_quantity', 'is_active', 'unit']
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else None


class BulkProductUpdateSerializer(serializers.Serializer):
    """Serializer for bulk product updates"""
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    update_data = serializers.DictField()


class ProductStatisticsSerializer(serializers.Serializer):
    """Serializer for product statistics"""
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    low_stock_products = serializers.IntegerField()
    out_of_stock_products = serializers.IntegerField()
    total_inventory_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_products_value = serializers.DecimalField(max_digits=12, decimal_places=2)
