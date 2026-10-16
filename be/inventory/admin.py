from django.contrib import admin
from .models import StockCheckpoint, StockCheckpointLine, StockLayer, StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'movement_type', 'quantity', 'stock_before', 'stock_after',
        'unit_cost', 'total_cost', 'user', 'reference', 'created_at'
    ]
    list_filter = ['movement_type', 'created_at']
    search_fields = ['product__name', 'product__sku', 'reference', 'notes']
    readonly_fields = ['created_at', 'total_cost', 'stock_before', 'stock_after']
    fieldsets = (
        ('Movement Details', {
            'fields': (
                'product', 'movement_type', 'quantity',
                'stock_before', 'stock_after', 'unit_cost', 'total_cost',
            )
        }),
        ('Additional Info', {
            'fields': ('reference', 'notes', 'user', 'created_at')
        }),
    )


@admin.register(StockLayer)
class StockLayerAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'variant', 'qty_remaining', 'qty_received',
        'unit_cost', 'unit_sell_price', 'received_at',
    ]
    list_filter = ['received_at']
    search_fields = ['product__name', 'product__sku']
    readonly_fields = ['created_at']


class StockCheckpointLineInline(admin.TabularInline):
    model = StockCheckpointLine
    extra = 0
    readonly_fields = [
        'product', 'variant', 'system_qty_at_open', 'counted_qty',
        'unit_cost_snapshot', 'status', 'counted_at', 'counted_by', 'movement',
    ]
    can_delete = False


@admin.register(StockCheckpoint)
class StockCheckpointAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'opened_at', 'opened_by', 'closed_at', 'closed_by']
    list_filter = ['status', 'opened_at']
    search_fields = ['title', 'notes']
    readonly_fields = ['opened_at', 'opened_by', 'closed_at', 'closed_by']
    inlines = [StockCheckpointLineInline]
