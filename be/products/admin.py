from django.contrib import admin
from .models import Category, Product, Size, Color, ProductVariant


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'display_order', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code']
    ordering = ['display_order', 'name']


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ['name', 'hex_code', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    fields = ['name', 'parent', 'description', 'is_active', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ['size', 'color', 'sku', 'barcode', 'price', 'cost', 'stock_quantity', 'is_active']
    readonly_fields = ['sku']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'sku', 'category', 'subcategory', 'has_variants', 'price', 'cost', 'stock_quantity',
        'unit', 'is_active', 'track_stock', 'created_at'
    ]
    list_filter = [
        'category', 'subcategory', 'has_variants', 'is_active', 'track_stock', 'is_taxable',
        'unit', 'created_at'
    ]
    search_fields = ['name', 'sku', 'barcode', 'supplier']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['available_sizes', 'available_colors']
    inlines = [ProductVariantInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'sku', 'barcode', 'category', 'subcategory', 'description', 'image')
        }),
        ('Variants', {
            'fields': ('has_variants', 'available_sizes', 'available_colors'),
            'description': 'Enable variants and select available sizes/colors for this product'
        }),
        ('Pricing', {
            'fields': ('price', 'cost', 'tax_rate', 'is_taxable')
        }),
        ('Inventory', {
            'fields': (
                'track_stock', 'stock_quantity', 'unit',
                'low_stock_threshold', 'reorder_quantity'
            )
        }),
        ('Supplier', {
            'fields': ('supplier', 'supplier_contact')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'size', 'color', 'sku', 'price', 'cost', 'stock_quantity', 'is_active']
    list_filter = ['is_active', 'product', 'size', 'color']
    search_fields = ['product__name', 'sku', 'barcode']
    readonly_fields = ['sku', 'created_at', 'updated_at']
