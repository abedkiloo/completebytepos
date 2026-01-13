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
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode', 
            'category', 'category_name', 'category_detail',
            'subcategory', 'subcategory_name', 'subcategory_detail',
            'has_variants', 'available_sizes', 'available_sizes_detail',
            'available_colors', 'available_colors_detail', 'variants',
            'price', 'cost', 'stock_quantity', 'low_stock_threshold', 'reorder_quantity',
            'unit', 'image', 'image_url', 'description', 'supplier', 'supplier_contact',
            'tax_rate', 'is_taxable', 'track_stock', 'is_low_stock', 'needs_reorder',
            'profit_margin', 'profit_amount', 'total_value', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'sku']
    
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
        
        # If updating, use instance values if not provided in data
        if self.instance:
            if category_id is None:
                category_id = self.instance.category_id
            if subcategory_id is None:
                subcategory_id = self.instance.subcategory_id
        
        if subcategory_id and category_id:
            # Fetch the actual Category objects to check parent relationship
            from .models import Category
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
        
        # Create product instance with error handling
        try:
            product = Product.objects.create(**validated_data)
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
        
        # Ensure category and subcategory are IDs, not objects
        if 'category' in validated_data:
            category = validated_data['category']
            if category and hasattr(category, 'id'):
                validated_data['category'] = category.id
            elif category == '' or category is None:
                validated_data['category'] = None
        
        if 'subcategory' in validated_data:
            subcategory = validated_data['subcategory']
            if subcategory and hasattr(subcategory, 'id'):
                validated_data['subcategory'] = subcategory.id
            elif subcategory == '' or subcategory is None:
                validated_data['subcategory'] = None
        
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
