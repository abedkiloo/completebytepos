from rest_framework import serializers
from .models import StockMovement
from products.serializers import ProductListSerializer, ProductVariantSerializer


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_detail = ProductListSerializer(source='product', read_only=True)
    variant_detail = ProductVariantSerializer(source='variant', read_only=True)
    variant_info = serializers.SerializerMethodField()
    user_name = serializers.CharField(source='user.username', read_only=True)
    stock_delta = serializers.SerializerMethodField()
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'product_detail',
            'variant', 'variant_detail', 'variant_info',
            'movement_type', 'quantity', 'stock_delta', 'unit_cost', 'total_cost',
            'reference', 'notes', 'user', 'user_name',
            'stock_before', 'stock_after', 'created_at'
        ]
        read_only_fields = ['created_at', 'total_cost', 'stock_before', 'stock_after', 'stock_delta']
    
    def get_variant_info(self, obj):
        """Get variant information as string"""
        if obj.variant:
            parts = []
            if obj.variant.size:
                parts.append(f"Size: {obj.variant.size.name}")
            if obj.variant.color:
                parts.append(f"Color: {obj.variant.color.name}")
            return " - ".join(parts) if parts else None
        return None

    def get_stock_delta(self, obj):
        """Signed change this movement applied to on-hand stock."""
        return obj._stock_delta()

    def to_representation(self, instance):
        from inventory.module_settings import apply_stock_movement_representation_flags

        return apply_stock_movement_representation_flags(super().to_representation(instance))


class StockAdjustmentSerializer(serializers.Serializer):
    """Serializer for stock adjustments"""
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)


class StockPurchaseSerializer(serializers.Serializer):
    """Serializer for stock purchases"""
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)
    unit_cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class StockTransferSerializer(serializers.Serializer):
    """Serializer for stock transfers between branches"""
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    to_branch_id = serializers.IntegerField(required=True)
    reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class BulkStockAdjustmentSerializer(serializers.Serializer):
    """Serializer for bulk stock adjustments"""
    adjustments = serializers.ListField(
        child=serializers.DictField(),
        min_length=1
    )


class InventoryReportSerializer(serializers.Serializer):
    """Serializer for inventory reports"""
    total_products = serializers.IntegerField()
    tracked_products = serializers.IntegerField()
    low_stock_count = serializers.IntegerField()
    out_of_stock_count = serializers.IntegerField()
    total_inventory_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_movements_today = serializers.IntegerField()
    total_movements_this_month = serializers.IntegerField()
    by_movement_type = serializers.ListField(required=False)
    recent_movements = serializers.ListField(required=False)
