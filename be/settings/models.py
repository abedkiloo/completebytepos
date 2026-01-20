from django.db import models
from django.contrib.auth.models import User


class ModuleSettings(models.Model):
    """Module enablement settings - only super admins can modify"""
    MODULE_CHOICES = [
        ('products', 'Products Management'),
        ('sales', 'Sales'),
        ('customers', 'Customer Management'),
        ('suppliers', 'Supplier Management'),
        ('employees', 'Employee Management'),
        ('invoicing', 'Invoicing'),
        ('inventory', 'Inventory Management'),
        ('stock', 'Stock Management'),
        ('expenses', 'Expenses'),
        ('income', 'Income'),
        ('bank_accounts', 'Bank Accounts'),
        ('money_transfer', 'Money Transfer'),
        ('accounting', 'Accounting'),
        ('balance_sheet', 'Balance Sheet'),
        ('trial_balance', 'Trial Balance'),
        ('cash_flow', 'Cash Flow'),
        ('account_statement', 'Account Statement'),
        ('barcodes', 'Barcodes'),
        ('reports', 'Reports'),
        ('settings', 'System Settings'),
    ]

    module_name = models.CharField(max_length=50, choices=MODULE_CHOICES, unique=True)
    is_enabled = models.BooleanField(default=True, help_text='Enable or disable this module')
    description = models.TextField(blank=True, help_text='Module description')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modules_updated'
    )

    class Meta:
        verbose_name = "Module Setting"
        verbose_name_plural = "Module Settings"
        ordering = ['module_name']
        db_table = 'accounts_modulesettings'  # Keep old table name for backward compatibility

    def __str__(self):
        return f"{self.get_module_name_display()} - {'Enabled' if self.is_enabled else 'Disabled'}"

    @classmethod
    def is_module_enabled(cls, module_name):
        """Check if a module is enabled"""
        try:
            module = cls.objects.get(module_name=module_name)
            return module.is_enabled
        except cls.DoesNotExist:
            # Default to enabled if not configured
            return True


class ModuleFeature(models.Model):
    """Granular feature settings within modules - allows enabling/disabling specific features"""
    MODULE_FEATURES = {
        'products': [
            ('qr_printing', 'QR Code Printing'),
            ('barcode_printing', 'Barcode Printing'),
            ('product_variants', 'Product Variants (Sizes/Colors)'),
            ('product_images', 'Product Images'),
            ('bulk_operations', 'Bulk Operations'),
            ('csv_import_export', 'CSV Import/Export'),
        ],
        'inventory': [
            ('stock_adjustments', 'Stock Adjustments'),
            ('stock_transfers', 'Stock Transfers'),
            ('low_stock_alerts', 'Low Stock Alerts'),
            ('reorder_points', 'Reorder Points'),
            ('inventory_reports', 'Inventory Reports'),
        ],
        'sales': [
            ('pos', 'Point of Sale (POS)'),
            ('normal_sale', 'Normal Sale'),
            ('sales_history', 'Sales History'),
            ('receipt_printing', 'Receipt Printing'),
        ],
        'customers': [
            ('customer_management', 'Customer Management'),
            ('customer_history', 'Customer Purchase History'),
            ('customer_reports', 'Customer Reports'),
            ('barcode_check', 'Barcode Check'),
            ('qr_code_check', 'QR Code Check'),
        ],
        'suppliers': [
            ('supplier_management', 'Supplier Management'),
            ('supplier_products', 'Supplier Products'),
            ('supplier_reports', 'Supplier Reports'),
            ('supplier_purchases', 'Supplier Purchase History'),
            ('credit_management', 'Credit Management'),
        ],
        'invoicing': [
            ('invoice_creation', 'Invoice Creation'),
            ('invoice_tracking', 'Invoice Tracking'),
            ('payment_tracking', 'Payment Tracking'),
            ('partial_payments', 'Partial Payments'),
            ('invoice_reports', 'Invoice Reports'),
        ],
        'barcodes': [
            ('barcode_generation', 'Barcode Generation'),
            ('qr_generation', 'QR Code Generation'),
            ('label_printing', 'Label Printing'),
            ('bulk_generation', 'Bulk Generation'),
        ],
        'reports': [
            ('sales_reports', 'Sales Reports'),
            ('product_reports', 'Product Reports'),
            ('inventory_reports', 'Inventory Reports'),
            ('financial_reports', 'Financial Reports'),
        ],
        'accounting': [
            ('chart_of_accounts', 'Chart of Accounts'),
            ('journal_entries', 'Journal Entries'),
            ('balance_sheet', 'Balance Sheet'),
            ('income_statement', 'Income Statement'),
            ('trial_balance', 'Trial Balance'),
            ('general_ledger', 'General Ledger'),
        ],
        'stock': [
            ('manage_stock', 'Manage Stock'),
            ('stock_adjustments', 'Stock Adjustments'),
            ('stock_transfers', 'Stock Transfers'),
            ('stock_reports', 'Stock Reports'),
            ('low_stock_alerts', 'Low Stock Alerts'),
        ],
        'settings': [
            ('user_management', 'User Management'),
            ('role_management', 'Role Management'),
            ('permission_management', 'Permission Management'),
            ('module_settings', 'Module Settings'),
            ('system_configuration', 'System Configuration'),
            ('multi_branch_support', 'Multi-Branch Support'),
        ],
    }

    module = models.ForeignKey(
        ModuleSettings,
        on_delete=models.CASCADE,
        related_name='features',
        help_text='Parent module'
    )
    feature_key = models.CharField(max_length=100, help_text='Feature identifier (e.g., qr_printing)')
    feature_name = models.CharField(max_length=200, help_text='Feature display name')
    is_enabled = models.BooleanField(default=True, help_text='Enable or disable this feature')
    description = models.TextField(blank=True, help_text='Feature description')
    display_order = models.IntegerField(default=0, help_text='Order for display in UI')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='features_updated'
    )

    class Meta:
        verbose_name = "Module Feature"
        verbose_name_plural = "Module Features"
        unique_together = [['module', 'feature_key']]
        ordering = ['module', 'display_order', 'feature_name']
        db_table = 'accounts_modulefeature'  # Keep old table name for backward compatibility

    def __str__(self):
        return f"{self.module.get_module_name_display()} - {self.feature_name} ({'Enabled' if self.is_enabled else 'Disabled'})"

    @classmethod
    def is_feature_enabled(cls, module_name, feature_key):
        """Check if a specific feature within a module is enabled"""
        try:
            module = ModuleSettings.objects.get(module_name=module_name)
            if not module.is_enabled:
                return False
            feature = cls.objects.get(module=module, feature_key=feature_key)
            return feature.is_enabled
        except (ModuleSettings.DoesNotExist, cls.DoesNotExist):
            # Default to enabled if not configured
            return True


class Tenant(models.Model):
    """Tenant model representing a Business/Company"""
    name = models.CharField(max_length=200, db_index=True, help_text='Business/Company name')
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text='Unique tenant code')
    registration_number = models.CharField(max_length=100, blank=True, help_text='Business registration number')
    tax_id = models.CharField(max_length=50, blank=True, help_text='Tax ID or VAT number')
    address = models.TextField(blank=True, help_text='Business address')
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True, help_text='Whether this tenant is active')
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_tenants',
        help_text='Primary owner/administrator of this business'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tenants_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @classmethod
    def get_default_tenant(cls):
        """Get the default/active tenant (for single-tenant systems)"""
        try:
            return cls.objects.filter(is_active=True).first()
        except:
            return None


class Branch(models.Model):
    """Branch model - Physical or logical outlet under a Tenant (Business/Company)"""
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='branches',
        help_text='Business/Company this branch belongs to'
    )
    branch_code = models.CharField(max_length=50, db_index=True, help_text='Unique branch code within tenant')
    name = models.CharField(max_length=200, db_index=True, help_text='Branch name')
    address = models.TextField(blank=True, help_text='Branch address')
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True, help_text='Whether this branch is active')
    is_headquarters = models.BooleanField(default=False, help_text='Mark as headquarters/main branch for this tenant')
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_branches',
        help_text='Branch manager'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='branches_created'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Branch"
        verbose_name_plural = "Branches"
        ordering = ['tenant', 'name']
        unique_together = [['tenant', 'branch_code']]  # Branch code unique within tenant
        indexes = [
            models.Index(fields=['tenant', 'branch_code']),
            models.Index(fields=['tenant', 'name']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_headquarters']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.branch_code}) - {self.tenant.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one branch per tenant can be marked as headquarters
        if self.is_headquarters:
            Branch.objects.filter(
                tenant=self.tenant,
                is_headquarters=True
            ).exclude(pk=self.pk).update(is_headquarters=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_headquarters(cls, tenant=None):
        """Get the headquarters branch for a tenant"""
        queryset = cls.objects.filter(is_headquarters=True, is_active=True)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        try:
            return queryset.first()
        except:
            return None
    
    @classmethod
    def get_active_branches(cls, tenant=None):
        """Get all active branches, optionally filtered by tenant"""
        queryset = cls.objects.filter(is_active=True)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset.order_by('name')
