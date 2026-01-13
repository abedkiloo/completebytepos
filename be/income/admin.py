from django.contrib import admin
from .models import IncomeCategory, Income


@admin.register(IncomeCategory)
class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = [
        'income_number', 'category', 'amount', 'income_date',
        'status', 'payment_method', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'category', 'income_date']
    search_fields = ['income_number', 'description', 'payer', 'reference_number']
    readonly_fields = ['income_number', 'created_at', 'updated_at']
    date_hierarchy = 'income_date'
    ordering = ['-income_date', '-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('income_number', 'category', 'amount', 'income_date', 'description')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'payer', 'reference_number')
        }),
        ('Status & Approval', {
            'fields': ('status', 'created_by', 'approved_by', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
