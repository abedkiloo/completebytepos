from rest_framework import serializers
from products.stock_utils import apply_catalog_variant_representation
from .models import Category, Product, Size, Color, ProductVariant, UnitOfMeasure


def _map_selling_price_fields(data):
    """Accept ``selling_price`` from clients; store on ``price`` column."""
    if not hasattr(data, 'copy'):
        data = dict(data)
    else:
        data = data.copy()
    if 'selling_price' in data and data.get('selling_price') not in (None, ''):
        data['price'] = data['selling_price']
    return data


def _apply_product_financial_defaults(data, *, instance=None):
    """
    ``Product.price`` is NOT NULL — default omitted values on create.
    On partial update, drop explicit nulls so we do not clear existing amounts.
    """
    from decimal import Decimal

    zero = Decimal('0')
    if instance is None:
        for field in ('price', 'mrp', 'cost'):
            if data.get(field) is None:
                data[field] = zero
        return data
    for field in ('price', 'mrp', 'cost'):
        if field in data and data[field] is None:
            data.pop(field)
    return data


def _related_obj_name(obj_or_id, model_cls):
    if obj_or_id is None:
        return None
    if hasattr(obj_or_id, 'name'):
        return obj_or_id.name
    try:
        row = model_cls.objects.filter(pk=obj_or_id).first()
        return row.name if row else None
    except (TypeError, ValueError):
        return None


def _variant_validation_label(instance=None, data=None):
    """Human-readable size/color (or SKU) for validation messages."""
    parts = []
    size_ref = data.get('size') if data else None
    color_ref = data.get('color') if data else None
    if instance is not None:
        if size_ref is None:
            size_ref = instance.size_id
        if color_ref is None:
            color_ref = instance.color_id
    size_name = _related_obj_name(size_ref, Size)
    color_name = _related_obj_name(color_ref, Color)
    if size_name:
        parts.append(size_name)
    if color_name:
        parts.append(color_name)
    if parts:
        return ' / '.join(parts)
    sku = (data or {}).get('sku')
    if not sku and instance is not None:
        sku = instance.sku
    if sku:
        return sku
    if instance is not None and instance.pk:
        return f'#{instance.pk}'
    return 'this variant'


def _resolve_variant_price(data, instance):
    if 'price' in data:
        val = data.get('price')
        if val is not None:
            return val
    if instance is not None:
        if instance.price is not None:
            return instance.price
        return instance.product.price
    product = data.get('product') if data else None
    if product is not None:
        return getattr(product, 'price', None)
    return None


def _resolve_variant_cost(data, instance):
    if 'cost' in data:
        val = data.get('cost')
        if val is not None:
            return val
    if instance is not None:
        if instance.cost is not None:
            return instance.cost
        return instance.product.cost
    product = data.get('product') if data else None
    if product is not None:
        return getattr(product, 'cost', None)
    return None


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


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = [
            'id', 'code', 'label', 'is_active', 'display_order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_code(self, value):
        from products.units import normalize_unit_code

        code = normalize_unit_code(value)
        if not code:
            raise serializers.ValidationError('Unit code is required.')
        return code

    def create(self, validated_data):
        from products.units import create_unit

        return create_unit(validated_data['code'], validated_data['label'])


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for ProductVariant model"""
    size_name = serializers.CharField(source='size.name', read_only=True)
    size_code = serializers.CharField(source='size.code', read_only=True)
    color_name = serializers.CharField(source='color.name', read_only=True)
    color_hex = serializers.CharField(source='color.hex_code', read_only=True)
    selling_price = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    effective_mrp = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    effective_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'size', 'size_name', 'size_code',
            'color', 'color_name', 'color_hex',
            'sku', 'barcode', 'mrp', 'price', 'selling_price', 'cost',
            'effective_price', 'effective_mrp', 'effective_cost',
            'stock_quantity', 'low_stock_threshold',
            'is_low_stock', 'is_active',
            'created_at', 'updated_at'
        ]
        # NOTE: ``sku`` is intentionally writable. Clients may supply their
        # own SKU convention (e.g. ``DRINK-COKE-500ML-L``). The model's
        # ``save()`` auto-generates a UUID-based SKU only when none is
        # supplied. Making ``sku`` read-only would silently drop the user's
        # value AND disable the duplicate-SKU validator below.
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'sku': {'required': False, 'allow_blank': True},
            'price': {'required': False, 'allow_null': True},
            'product': {'required': False},
            'size': {'required': False, 'allow_null': True},
            'color': {'required': False, 'allow_null': True},
        }

    def to_internal_value(self, data):
        return super().to_internal_value(_map_selling_price_fields(data))

    def validate(self, data):
        from accounts.sensitive_edits import (
            sales_catalog_mode_active,
            user_may_edit_financial_fields,
        )

        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        catalog_skip = bool(user and sales_catalog_mode_active(user))
        if user and not user_may_edit_financial_fields(user):
            catalog_skip = True
        if catalog_skip:
            return data

        label = _variant_validation_label(self.instance, data)
        price = _resolve_variant_price(data, self.instance)
        cost = _resolve_variant_cost(data, self.instance)
        mrp = data.get('mrp')
        if mrp is None and self.instance is not None:
            mrp = self.instance.mrp

        if price is not None and cost is not None and price < cost:
            raise serializers.ValidationError({
                'price': (
                    'Selling price should be greater than or equal to cost price '
                    f'for variant {label}.'
                )
            })
        if mrp is not None and price is not None and mrp > 0 and mrp < price:
            raise serializers.ValidationError({
                'mrp': f'MRP should be at least the selling price for variant {label}.'
            })
        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from approvals.effective import apply_approved_variant_overlay

        return apply_approved_variant_overlay(instance, data)

    def create(self, validated_data):
        variant = super().create(validated_data)
        # Ensure parent product stock and cost stay in sync when variants change
        try:
            from products.stock_utils import sync_product_stock_from_variants, sync_product_cost_from_variants
            prod = variant.product
            if prod and prod.has_variants and prod.track_stock:
                sync_product_stock_from_variants(prod)
                sync_product_cost_from_variants(prod)
        except Exception:
            # Do not surface sync errors to client; keep create successful
            pass
        return variant

    def update(self, instance, validated_data):
        variant = super().update(instance, validated_data)
        try:
            from products.stock_utils import sync_product_stock_from_variants, sync_product_cost_from_variants
            prod = variant.product
            if prod and prod.has_variants and prod.track_stock:
                sync_product_stock_from_variants(prod)
                sync_product_cost_from_variants(prod)
        except Exception:
            pass
        return variant


class NestedProductVariantSerializer(ProductVariantSerializer):
    """Nested on product create/update — parent supplies product on save."""

    class Meta(ProductVariantSerializer.Meta):
        fields = [
            f for f in ProductVariantSerializer.Meta.fields
            if f != 'product'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('size', 'color'):
            field = self.fields.get(name)
            if field is not None:
                field.required = False
                field.allow_null = True


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    linked_product_count = serializers.SerializerMethodField()
    can_move_parent = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'parent', 'is_active',
            'product_count', 'children_count', 'linked_product_count',
            'can_move_parent', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def _attempted_parent_id(self):
        if 'parent' in self.initial_data:
            raw = self.initial_data.get('parent')
            if raw in (None, ''):
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
        if self.instance is not None:
            return self.instance.parent_id
        return None

    def validate_name(self, value):
        from products.category_validation import normalize_category_name, find_duplicate_category

        normalized = normalize_category_name(value)
        if not normalized:
            raise serializers.ValidationError('Category name is required.')
        existing = find_duplicate_category(
            normalized,
            exclude_pk=self.instance.pk if self.instance else None,
        )
        if existing:
            from products.category_validation import DuplicateCategoryInfo

            raise serializers.ValidationError(
                DuplicateCategoryInfo(existing).user_message(
                    normalized,
                    attempted_parent_id=self._attempted_parent_id(),
                )
            )
        return normalized
    
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

    def get_linked_product_count(self, obj):
        from products.category_validation import category_linked_product_count

        return category_linked_product_count(obj)

    def get_can_move_parent(self, obj):
        from products.category_validation import subcategory_parent_movable

        return subcategory_parent_movable(obj)

    def validate(self, data):
        parent = data.get('parent', getattr(self.instance, 'parent', None))
        if parent is not None and hasattr(parent, 'parent_id') and parent.parent_id:
            raise serializers.ValidationError({
                'parent': 'Parent must be a top-level category, not another subcategory.',
            })
        if self.instance and self.instance.children.exists():
            new_parent = data.get('parent', self.instance.parent_id)
            if new_parent and new_parent != self.instance.parent_id:
                raise serializers.ValidationError({
                    'parent': 'Cannot change parent on a category that already has subcategories.',
                })
        if self.instance and self.instance.parent_id is not None and 'parent' in data:
            from products.category_validation import subcategory_parent_movable

            new_parent = data.get('parent')
            if new_parent != self.instance.parent_id and not subcategory_parent_movable(
                self.instance
            ):
                raise serializers.ValidationError({
                    'parent': (
                        'Cannot move this subcategory — products are already linked. '
                        'Reassign or remove those products first.'
                    ),
                })
        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from approvals.effective import apply_approved_category_overlay

        return apply_approved_category_overlay(instance, data)


class CategoryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for category lists"""
    product_count = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    linked_product_count = serializers.SerializerMethodField()
    can_move_parent = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'parent', 'is_active',
            'product_count', 'children_count', 'linked_product_count',
            'can_move_parent',
        ]

    def get_product_count(self, obj):
        if hasattr(obj, 'products'):
            return obj.products.count()
        return obj.products.filter(is_active=True).count()

    def get_children_count(self, obj):
        if hasattr(obj, 'children'):
            return obj.children.count()
        return obj.children.all().count()

    def get_linked_product_count(self, obj):
        from products.category_validation import category_linked_product_count

        return category_linked_product_count(obj)

    def get_can_move_parent(self, obj):
        from products.category_validation import subcategory_parent_movable

        return subcategory_parent_movable(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from approvals.effective import apply_approved_category_overlay

        return apply_approved_category_overlay(instance, data)


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    category_detail = serializers.SerializerMethodField()
    subcategory_name = serializers.SerializerMethodField()
    subcategory_detail = serializers.SerializerMethodField()
    available_sizes_detail = SizeSerializer(source='available_sizes', many=True, read_only=True)
    available_colors_detail = ColorSerializer(source='available_colors', many=True, read_only=True)
    variants = NestedProductVariantSerializer(many=True, required=False)
    is_low_stock = serializers.BooleanField(read_only=True)
    profit_margin = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    profit_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_value = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    needs_reorder = serializers.BooleanField(read_only=True)
    image_url = serializers.SerializerMethodField()
    supplier_name_display = serializers.SerializerMethodField()
    supplier_detail = serializers.SerializerMethodField()
    selling_price = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, required=False
    )
    variant_combinations = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode', 
            'category', 'category_name', 'category_detail',
            'subcategory', 'subcategory_name', 'subcategory_detail',
            'has_variants', 'available_sizes', 'available_sizes_detail',
            'available_colors', 'available_colors_detail', 'variant_combinations', 'variants',
            'mrp', 'price', 'selling_price', 'cost', 'stock_quantity', 'low_stock_threshold', 'reorder_quantity',
            'unit', 'image', 'image_url', 'description', 
            'supplier', 'supplier_name', 'supplier_name_display', 'supplier_detail', 'supplier_contact',
            'tax_rate', 'is_taxable', 'track_stock', 'is_low_stock', 'needs_reorder',
            'profit_margin', 'profit_amount', 'total_value', 'is_active',
            'created_at', 'updated_at'
        ]
        # NOTE: ``sku`` is intentionally writable - see ProductVariantSerializer
        # for the same rationale. Marking it read-only silently discarded
        # client-supplied SKUs and disabled the ``validate_sku`` duplicate
        # check on the same serializer.
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'sku': {'required': False, 'allow_blank': True},
            'price': {'required': False},
            'mrp': {'required': False},
            'cost': {'required': False},
        }
    
    def to_internal_value(self, data):
        """Convert category/subcategory objects to IDs if needed"""
        data = _map_selling_price_fields(data)
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
        
        if 'variant_combinations' in data:
            from products.variant_combinations import normalize_variant_combinations

            self._variant_combinations = normalize_variant_combinations(
                data.get('variant_combinations')
            )
            data = data.copy() if hasattr(data, 'copy') else dict(data)
            data.pop('variant_combinations', None)
        elif not hasattr(self, '_variant_combinations'):
            self._variant_combinations = None

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
            from config.media_urls import absolute_media_url
            return absolute_media_url(self.context.get('request'), obj.image.url)
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
        """Validate product data; sales staff cannot change pricing or stock levels."""
        from accounts.sensitive_edits import (
            sales_catalog_mode_active,
            user_may_edit_financial_fields,
        )
        from products.catalog_rules import apply_sales_catalog_rules

        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        catalog_skip = bool(user and sales_catalog_mode_active(user))
        if user:
            apply_sales_catalog_rules(
                data,
                user=user,
                is_create=self.instance is None,
                instance=self.instance,
            )

        if user and not user_may_edit_financial_fields(user):
            catalog_skip = True

        has_variants = data.get('has_variants')
        if has_variants is None and self.instance is not None:
            has_variants = self.instance.has_variants

        price = data.get('price')
        if price is None and self.instance is not None:
            price = self.instance.price
        cost = data.get('cost')
        if cost is None and self.instance is not None:
            cost = self.instance.cost
        if (
            not has_variants
            and not catalog_skip
            and price is not None
            and cost is not None
            and price < cost
        ):
            raise serializers.ValidationError({
                'price': 'Selling price should be greater than or equal to cost price.'
            })
        mrp = data.get('mrp')
        if mrp is None and self.instance is not None:
            mrp = self.instance.mrp
        if (mrp is None or mrp == 0) and price is not None and not catalog_skip:
            data['mrp'] = price
            mrp = data['mrp']
        if (
            not has_variants
            and mrp is not None
            and price is not None
            and mrp > 0
            and mrp < price
        ):
            raise serializers.ValidationError(
                {'mrp': 'MRP should be at least the selling price.'}
            )
        
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
        
        from products.module_settings import products_show_cost_price, products_show_mrp
        from products.status_rules import strip_product_status_from_write_data

        if not products_show_cost_price():
            data.pop('cost', None)
        if not products_show_mrp():
            data.pop('mrp', None)

        if 'unit' in data:
            from products.units import validate_unit_code

            data['unit'] = validate_unit_code(data.get('unit'))

        data = _apply_product_financial_defaults(data, instance=self.instance)
        return strip_product_status_from_write_data(data)

    def to_representation(self, instance):
        from approvals.effective import apply_approved_product_overlay
        from products.module_settings import apply_product_list_representation_flags

        data = super().to_representation(instance)
        data = apply_catalog_variant_representation(instance, data)
        data = apply_approved_product_overlay(instance, data)
        return apply_product_list_representation_flags(data)

    def create(self, validated_data):
        """Create product instance, handling ManyToMany fields separately"""
        validated_data.pop('variant_combinations', None)
        # Extract nested variants payload if provided
        variants_payload = validated_data.pop('variants', None)
        # Extract ManyToMany fields
        available_sizes = validated_data.pop('available_sizes', [])
        available_colors = validated_data.pop('available_colors', [])
        # Prevent setting parent-level stock on create when variants will own stock.
        if validated_data.get('has_variants'):
            for _f in ('stock_quantity', 'low_stock_threshold', 'reorder_quantity'):
                validated_data.pop(_f, None)
        
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
            # Create product inside a transaction so nested variants can be
            # created atomically alongside the product.
            from django.db import transaction

            with transaction.atomic():
                product = Product.objects.create(
                    category=category,
                    subcategory=subcategory,
                    supplier=supplier,
                    **validated_data
                )

                # Create nested variants if provided
                if variants_payload:
                    for v in variants_payload:
                        variant_ser = ProductVariantSerializer(context=self.context)
                        variant_ser.create({**v, 'product': product})
                # After creating variants, sync parent stock and cost
                try:
                    from products.stock_utils import sync_product_stock_from_variants, sync_product_cost_from_variants
                    if product.has_variants and product.track_stock:
                        sync_product_stock_from_variants(product)
                        sync_product_cost_from_variants(product)
                except Exception:
                    pass
        except ValueError as e:
            # Convert model validation errors to serializer validation errors
            error_msg = str(e)
            # Check if it's a subcategory validation error
            if 'subcategory' in error_msg.lower():
                raise serializers.ValidationError({
                    'subcategory': error_msg
                })
            raise serializers.ValidationError(error_msg)
        except Exception as e:
            # Catch DB integrity errors such as duplicate SKU/barcode and
            # present them as serializer validation errors.
            from django.db import IntegrityError

            if isinstance(e, IntegrityError):
                raise serializers.ValidationError(str(e))
            raise
        
        # Set ManyToMany fields
        if available_sizes:
            product.available_sizes.set(available_sizes)
        if available_colors:
            product.available_colors.set(available_colors)
        
        return product
    
    def update(self, instance, validated_data):
        """Update product instance, handling ManyToMany fields separately"""
        validated_data.pop('variant_combinations', None)
        # Extract nested variants payload if provided
        variants_payload = validated_data.pop('variants', None)
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
        except Exception as e:
            from django.db import IntegrityError

            if isinstance(e, IntegrityError):
                raise serializers.ValidationError(str(e))
            raise
        
        # Update ManyToMany fields if provided
        if available_sizes is not None:
            instance.available_sizes.set(available_sizes)
        if available_colors is not None:
            instance.available_colors.set(available_colors)

        # Process nested variant updates/creates
        if variants_payload:
            from django.db import transaction

            with transaction.atomic():
                for v in variants_payload:
                    vid = v.get('id')
                    if vid not in (None, ''):
                        try:
                            variant_obj = ProductVariant.objects.get(
                                id=int(vid), product=instance
                            )
                            patch = {k: val for k, val in v.items() if k != 'id'}
                            ProductVariantSerializer(
                                instance=variant_obj, context=self.context
                            ).update(variant_obj, patch)
                            continue
                        except (ProductVariant.DoesNotExist, ValueError, TypeError):
                            pass
                    create_data = {k: val for k, val in v.items() if k != 'id'}
                    variant_ser = ProductVariantSerializer(context=self.context)
                    variant_ser.create({**create_data, 'product': instance})
            # After processing nested variants, ensure cost is synced
            try:
                from products.stock_utils import sync_product_cost_from_variants
                if instance.has_variants and instance.track_stock:
                    sync_product_cost_from_variants(instance)
            except Exception:
                pass

        # Sync parent stock from variants if applicable
        if instance.has_variants and instance.track_stock:
            from products.stock_utils import sync_product_stock_from_variants

            sync_product_stock_from_variants(instance)

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
    selling_price = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode',
            # Expose the raw FK IDs alongside the display names so the FE
            # (and tests) can filter / link without an extra round-trip.
            'category', 'category_name',
            'subcategory', 'subcategory_name',
            'has_variants',
            'available_sizes_detail', 'available_colors_detail',
            'mrp', 'price', 'selling_price', 'cost', 'stock_quantity', 'unit', 'track_stock',
            'is_low_stock', 'is_active', 'image_url'
        ]
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else None
    
    def get_subcategory_name(self, obj):
        return obj.subcategory.name if obj.subcategory else None
    
    def get_image_url(self, obj):
        if obj.image:
            from config.media_urls import absolute_media_url
            return absolute_media_url(self.context.get('request'), obj.image.url)
        return None

    def to_representation(self, instance):
        from approvals.effective import apply_approved_product_overlay
        from products.module_settings import apply_product_list_representation_flags

        data = super().to_representation(instance)
        data = apply_catalog_variant_representation(instance, data)
        if 'selling_price' not in data and data.get('price') is not None:
            data['selling_price'] = data['price']
        data = apply_approved_product_overlay(instance, data)
        return apply_product_list_representation_flags(data)


class ProductSearchSerializer(serializers.ModelSerializer):
    """Lightweight serializer for search results"""
    category_name = serializers.SerializerMethodField()
    has_variants = serializers.BooleanField(read_only=True)
    selling_price = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode', 'category_name', 'has_variants',
            'mrp', 'price', 'selling_price', 'stock_quantity', 'is_active', 'unit',
        ]
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def to_representation(self, instance):
        from approvals.effective import apply_approved_product_overlay
        from products.module_settings import apply_product_list_representation_flags

        data = super().to_representation(instance)
        data = apply_catalog_variant_representation(instance, data)
        if 'selling_price' not in data and data.get('price') is not None:
            data['selling_price'] = data['price']
        data = apply_approved_product_overlay(instance, data)
        return apply_product_list_representation_flags(data)


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
    # Legacy keys retained for backwards compatibility.
    low_stock_products = serializers.IntegerField()
    out_of_stock_products = serializers.IntegerField()
    # Canonical ``_count`` aliases used by the Reports hub and dashboard.
    low_stock_count = serializers.IntegerField()
    out_of_stock_count = serializers.IntegerField()
    total_inventory_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_products_value = serializers.DecimalField(max_digits=12, decimal_places=2)
