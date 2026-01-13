from django.contrib import admin
from .models import MoneyTransfer


@admin.register(MoneyTransfer)
class MoneyTransferAdmin(admin.ModelAdmin):
    list_display = [
        'transfer_number', 'transfer_type', 'from_account', 'to_account',
        'amount', 'currency', 'status', 'transfer_date', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'transfer_type', 'transfer_date']
    search_fields = ['transfer_number', 'description', 'reference']
    readonly_fields = ['transfer_number', 'created_at', 'updated_at']
    date_hierarchy = 'transfer_date'
    ordering = ['-transfer_date', '-created_at']
    
    fieldsets = (
        ('Transfer Information', {
            'fields': ('transfer_number', 'transfer_type', 'from_account', 'to_account', 'amount', 'currency')
        }),
        ('Details', {
            'fields': ('transfer_date', 'description', 'reference', 'fees', 'exchange_rate')
        }),
        ('Status & Approval', {
            'fields': ('status', 'created_by', 'approved_by', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
