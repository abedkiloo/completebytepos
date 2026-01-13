from django.contrib import admin
from .models import AccountType, Account, JournalEntry, Transaction


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'normal_balance', 'is_active']
    list_filter = ['is_active', 'normal_balance']
    ordering = ['name']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = [
        'account_code', 'name', 'account_type', 'current_balance',
        'is_active', 'parent'
    ]
    list_filter = ['account_type', 'is_active', 'parent']
    search_fields = ['account_code', 'name', 'description']
    readonly_fields = ['current_balance', 'created_at', 'updated_at']
    ordering = ['account_code']
    
    fieldsets = (
        ('Account Information', {
            'fields': ('account_code', 'name', 'account_type', 'parent', 'description')
        }),
        ('Balances', {
            'fields': ('opening_balance', 'current_balance')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = [
        'entry_number', 'entry_date', 'account', 'entry_type',
        'amount', 'reference', 'created_by', 'created_at'
    ]
    list_filter = ['entry_type', 'entry_date', 'account', 'reference_type']
    search_fields = ['entry_number', 'description', 'reference']
    readonly_fields = ['entry_number', 'created_at']
    date_hierarchy = 'entry_date'
    ordering = ['-entry_date', '-created_at']
    
    fieldsets = (
        ('Entry Information', {
            'fields': ('entry_number', 'entry_date', 'account', 'entry_type', 'amount', 'description')
        }),
        ('Reference', {
            'fields': ('reference', 'reference_type', 'reference_id')
        }),
        ('Created By', {
            'fields': ('created_by', 'created_at')
        }),
    )


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_number', 'transaction_date', 'description',
        'reference', 'created_by', 'created_at'
    ]
    list_filter = ['transaction_date', 'reference_type']
    search_fields = ['transaction_number', 'description', 'reference']
    readonly_fields = ['transaction_number', 'created_at']
    date_hierarchy = 'transaction_date'
    ordering = ['-transaction_date', '-created_at']
    filter_horizontal = ['journal_entries']
