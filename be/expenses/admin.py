from django.contrib import admin
from .models import ExpenseCategory, Expense


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        'expense_number', 'category', 'amount', 'expense_date',
        'status', 'payment_method', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'category', 'expense_date']
    search_fields = ['expense_number', 'description', 'vendor', 'receipt_number']
    readonly_fields = ['expense_number', 'created_at', 'updated_at']
    date_hierarchy = 'expense_date'
    ordering = ['-expense_date', '-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('expense_number', 'category', 'amount', 'expense_date', 'description')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'vendor', 'receipt_number')
        }),
        ('Status & Approval', {
            'fields': ('status', 'created_by', 'approved_by', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
