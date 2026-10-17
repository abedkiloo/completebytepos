from rest_framework import serializers

from inventory.models import StockCheckpoint, StockCheckpointLine


class StockCheckpointLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    variant_label = serializers.SerializerMethodField()
    counted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockCheckpointLine
        fields = [
            'id',
            'checkpoint',
            'product',
            'product_name',
            'product_sku',
            'variant',
            'variant_label',
            'system_qty_at_open',
            'counted_qty',
            'unit_cost_snapshot',
            'status',
            'counted_at',
            'counted_by',
            'counted_by_name',
            'movement',
        ]
        read_only_fields = fields

    def get_variant_label(self, obj):
        if not obj.variant_id:
            return None
        v = obj.variant
        parts = []
        if getattr(v, 'sku', None):
            parts.append(v.sku)
        size = getattr(getattr(v, 'size', None), 'name', None)
        color = getattr(getattr(v, 'color', None), 'name', None)
        if size:
            parts.append(size)
        if color:
            parts.append(color)
        return ' · '.join(parts) if parts else f'Variant #{v.id}'

    def get_counted_by_name(self, obj):
        if not obj.counted_by_id:
            return None
        u = obj.counted_by
        return u.get_full_name() or u.username


class StockCheckpointSerializer(serializers.ModelSerializer):
    opened_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()
    pending_line_count = serializers.SerializerMethodField()
    counted_line_count = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()
    lines = StockCheckpointLineSerializer(many=True, read_only=True)
    inventory_value_after = serializers.SerializerMethodField()

    class Meta:
        model = StockCheckpoint
        fields = [
            'id',
            'title',
            'status',
            'block_sales',
            'notes',
            'opened_at',
            'opened_by',
            'opened_by_name',
            'closed_at',
            'closed_by',
            'closed_by_name',
            'pending_line_count',
            'counted_line_count',
            'line_count',
            'inventory_value_after',
            'lines',
        ]
        read_only_fields = [
            'id',
            'status',
            'block_sales',
            'opened_at',
            'opened_by',
            'opened_by_name',
            'closed_at',
            'closed_by',
            'closed_by_name',
            'pending_line_count',
            'counted_line_count',
            'line_count',
            'inventory_value_after',
            'lines',
        ]

    def get_opened_by_name(self, obj):
        if not obj.opened_by_id:
            return None
        u = obj.opened_by
        return u.get_full_name() or u.username

    def get_closed_by_name(self, obj):
        if not obj.closed_by_id:
            return None
        u = obj.closed_by
        return u.get_full_name() or u.username

    def get_pending_line_count(self, obj):
        if 'pending_line_count' in obj.__dict__:
            return obj.__dict__['pending_line_count']
        return obj.lines.filter(status=StockCheckpointLine.STATUS_PENDING).count()

    def get_counted_line_count(self, obj):
        if 'counted_line_count' in obj.__dict__:
            return obj.__dict__['counted_line_count']
        return obj.lines.filter(status=StockCheckpointLine.STATUS_COUNTED).count()

    def get_line_count(self, obj):
        if '_line_count' in obj.__dict__:
            return obj.__dict__['_line_count']
        return obj.lines.count()

    def get_inventory_value_after(self, obj):
        """Sum counted_qty × unit_cost for counted lines (checkpoint stock value)."""
        total = 0
        for line in obj.lines.all():
            if line.status != StockCheckpointLine.STATUS_COUNTED or line.counted_qty is None:
                continue
            total += float(line.counted_qty) * float(line.unit_cost_snapshot or 0)
        return round(total, 2)


class StockCheckpointListSerializer(StockCheckpointSerializer):
    class Meta(StockCheckpointSerializer.Meta):
        fields = [
            f
            for f in StockCheckpointSerializer.Meta.fields
            if f != 'lines'
        ]


class OpenCheckpointSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    include_all_tracked = serializers.BooleanField(required=False, default=False)
    block_sales = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
        help_text='When omitted, uses inventory module setting block_sales_during_checkpoint.',
    )
    product_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )


class CountCheckpointLineSerializer(serializers.Serializer):
    counted_qty = serializers.IntegerField(min_value=0)
