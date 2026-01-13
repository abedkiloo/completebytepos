from django.contrib import admin
from .models import BankAccount, BankTransaction


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = [
        'account_name', 'account_number', 'bank_name',
        'account_type', 'current_balance', 'currency', 'is_active'
    ]
    list_filter = ['is_active', 'account_type', 'bank_name']
    search_fields = ['account_name', 'account_number', 'bank_name']
    readonly_fields = ['current_balance', 'created_at', 'updated_at']
    ordering = ['bank_name', 'account_name']
    
    fieldsets = (
        ('Account Information', {
            'fields': ('account_name', 'account_number', 'bank_name', 'account_type', 'branch', 'swift_code')
        }),
        ('Balances', {
            'fields': ('opening_balance', 'current_balance', 'currency')
        }),
        ('Status', {
            'fields': ('is_active', 'notes')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_number', 'bank_account', 'transaction_type',
        'amount', 'transaction_date', 'created_by', 'created_at'
    ]
    list_filter = ['transaction_type', 'transaction_date', 'bank_account']
    search_fields = ['transaction_number', 'description', 'reference']
    readonly_fields = ['transaction_number', 'created_at']
    date_hierarchy = 'transaction_date'
    ordering = ['-transaction_date', '-created_at']
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('transaction_number', 'bank_account', 'transaction_type', 'amount', 'description')
        }),
        ('Details', {
            'fields': ('reference', 'transaction_date')
        }),
        ('Created By', {
            'fields': ('created_by', 'created_at')
        }),
    )
