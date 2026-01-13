from django.contrib import admin
from .models import Sale, SaleItem, Invoice, InvoiceItem, Payment, Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_code', 'name', 'customer_type', 'phone', 'email', 'is_active', 'total_invoices', 'total_outstanding', 'created_at']
    list_filter = ['customer_type', 'is_active', 'created_at']
    search_fields = ['name', 'customer_code', 'email', 'phone', 'tax_id']
    readonly_fields = ['customer_code', 'total_invoices', 'total_outstanding', 'created_at', 'updated_at']
    fieldsets = (
        ('Customer Information', {
            'fields': ('customer_code', 'name', 'customer_type', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'address', 'city', 'country')
        }),
        ('Additional Information', {
            'fields': ('tax_id', 'notes', 'created_by')
        }),
        ('Statistics', {
            'fields': ('total_invoices', 'total_outstanding'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['subtotal']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['sale_number', 'cashier', 'total', 'payment_method', 'amount_paid', 'created_at']
    list_filter = ['payment_method', 'created_at']
    search_fields = ['sale_number', 'cashier__username']
    readonly_fields = ['sale_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    inlines = [SaleItemInline]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'subtotal']
    list_filter = ['sale__created_at']
    search_fields = ['sale__sale_number', 'product__name']


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ['subtotal']


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['created_at']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer', 'customer_name', 'total', 'amount_paid', 'balance', 'status', 'due_date', 'created_at']
    list_filter = ['status', 'created_at', 'due_date', 'customer']
    search_fields = ['invoice_number', 'customer__name', 'customer__customer_code', 'customer_name', 'customer_email', 'customer_phone']
    readonly_fields = ['invoice_number', 'balance', 'payment_percentage', 'is_fully_paid', 'is_overdue', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    inlines = [InvoiceItemInline, PaymentInline]
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'sale', 'status')
        }),
        ('Customer Information', {
            'fields': ('customer', 'customer_name', 'customer_email', 'customer_phone', 'customer_address')
        }),
        ('Financial Information', {
            'fields': ('subtotal', 'tax_amount', 'discount_amount', 'total', 'amount_paid', 'balance', 'payment_percentage')
        }),
        ('Dates', {
            'fields': ('issued_date', 'due_date')
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_by', 'is_fully_paid', 'is_overdue')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'product', 'quantity', 'unit_price', 'subtotal']
    list_filter = ['invoice__created_at']
    search_fields = ['invoice__invoice_number', 'product__name']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'payment_method', 'payment_date', 'reference', 'recorded_by', 'created_at']
    list_filter = ['payment_method', 'payment_date', 'created_at']
    search_fields = ['invoice__invoice_number', 'reference', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'payment_date'
