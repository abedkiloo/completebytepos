from django.contrib import admin
from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'supplier_code', 'supplier_type', 'contact_person', 'email', 'phone', 'is_preferred', 'is_active', 'rating', 'created_at']
    list_filter = ['supplier_type', 'is_preferred', 'is_active', 'payment_terms', 'rating']
    search_fields = ['name', 'supplier_code', 'email', 'phone', 'contact_person', 'tax_id']
    readonly_fields = ['supplier_code', 'created_at', 'updated_at', 'created_by']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'supplier_code', 'supplier_type', 'is_preferred', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'email', 'phone', 'alternate_phone')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Business Information', {
            'fields': ('tax_id', 'registration_number', 'website')
        }),
        ('Financial Information', {
            'fields': ('payment_terms', 'credit_limit', 'account_balance')
        }),
        ('Additional Information', {
            'fields': ('notes', 'rating')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
