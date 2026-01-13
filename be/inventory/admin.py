from django.contrib import admin
from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'movement_type', 'quantity', 'unit_cost', 'total_cost',
        'user', 'reference', 'created_at'
    ]
    list_filter = ['movement_type', 'created_at']
    search_fields = ['product__name', 'product__sku', 'reference', 'notes']
    readonly_fields = ['created_at', 'total_cost']
    fieldsets = (
        ('Movement Details', {
            'fields': ('product', 'movement_type', 'quantity', 'unit_cost', 'total_cost')
        }),
        ('Additional Info', {
            'fields': ('reference', 'notes', 'user', 'created_at')
        }),
    )
