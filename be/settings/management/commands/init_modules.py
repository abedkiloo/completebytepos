from django.core.management.base import BaseCommand
from settings.models import ModuleSettings, ModuleFeature


class Command(BaseCommand):
    help = 'Initialize module settings and features'

    def handle(self, *args, **options):
        self.stdout.write('Initializing module settings and features...')
        
        # Define all modules with their features
        modules_config = [
            {
                'module_name': 'products',
                'description': 'Product management module',
                'is_enabled': True,
                'features': [
                    {'key': 'qr_printing', 'name': 'QR Code Printing', 'description': 'Enable QR code generation and printing', 'order': 1},
                    {'key': 'barcode_printing', 'name': 'Barcode Printing', 'description': 'Enable barcode generation and printing', 'order': 2},
                    {'key': 'product_variants', 'name': 'Product Variants (Sizes/Colors)', 'description': 'Enable product variants with sizes and colors', 'order': 3},
                    {'key': 'product_images', 'name': 'Product Images', 'description': 'Enable product image uploads', 'order': 4},
                    {'key': 'bulk_operations', 'name': 'Bulk Operations', 'description': 'Enable bulk product operations', 'order': 5},
                    {'key': 'csv_import_export', 'name': 'CSV Import/Export', 'description': 'Enable CSV import and export', 'order': 6},
                ]
            },
            {
                'module_name': 'customers',
                'description': 'Customer management module',
                'is_enabled': True,
                'features': [
                    {'key': 'customer_management', 'name': 'Customer Management', 'description': 'Enable customer CRUD operations', 'order': 1},
                    {'key': 'customer_history', 'name': 'Customer Purchase History', 'description': 'Enable customer purchase history tracking', 'order': 2},
                    {'key': 'customer_reports', 'name': 'Customer Reports', 'description': 'Enable customer-related reports', 'order': 3},
                    {'key': 'barcode_check', 'name': 'Barcode Check', 'description': 'Enable barcode scanning for customer lookup', 'order': 4},
                    {'key': 'qr_code_check', 'name': 'QR Code Check', 'description': 'Enable QR code scanning for customer lookup', 'order': 5},
                ]
            },
            {
                'module_name': 'suppliers',
                'description': 'Supplier management module',
                'is_enabled': True,
                'features': [
                    {'key': 'supplier_management', 'name': 'Supplier Management', 'description': 'Enable supplier CRUD operations', 'order': 1},
                    {'key': 'supplier_products', 'name': 'Supplier Products', 'description': 'Enable viewing products by supplier', 'order': 2},
                    {'key': 'supplier_reports', 'name': 'Supplier Reports', 'description': 'Enable supplier-related reports', 'order': 3},
                    {'key': 'supplier_purchases', 'name': 'Supplier Purchase History', 'description': 'Enable supplier purchase history tracking', 'order': 4},
                    {'key': 'credit_management', 'name': 'Credit Management', 'description': 'Enable supplier credit limit and balance tracking', 'order': 5},
                ]
            },
            {
                'module_name': 'sales',
                'description': 'Sales management module',
                'is_enabled': True,
                'features': [
                    {'key': 'pos', 'name': 'Point of Sale (POS)', 'description': 'Enable POS system for quick sales', 'order': 1},
                    {'key': 'normal_sale', 'name': 'Normal Sale', 'description': 'Enable normal sales processing', 'order': 2},
                    {'key': 'sales_history', 'name': 'Sales History', 'description': 'Enable sales history tracking', 'order': 3},
                    {'key': 'receipt_printing', 'name': 'Receipt Printing', 'description': 'Enable receipt printing', 'order': 4},
                ]
            },
            {
                'module_name': 'invoicing',
                'description': 'Invoicing and payment tracking module',
                'is_enabled': True,
                'features': [
                    {'key': 'invoice_creation', 'name': 'Invoice Creation', 'description': 'Enable invoice creation from sales', 'order': 1},
                    {'key': 'invoice_tracking', 'name': 'Invoice Tracking', 'description': 'Enable invoice status tracking', 'order': 2},
                    {'key': 'payment_tracking', 'name': 'Payment Tracking', 'description': 'Enable payment tracking against invoices', 'order': 3},
                    {'key': 'partial_payments', 'name': 'Partial Payments', 'description': 'Enable partial payment processing', 'order': 4},
                    {'key': 'invoice_reports', 'name': 'Invoice Reports', 'description': 'Enable invoice-related reports', 'order': 5},
                ]
            },
            {
                'module_name': 'inventory',
                'description': 'Inventory management module',
                'is_enabled': True,
                'features': [
                    {'key': 'stock_adjustments', 'name': 'Stock Adjustments', 'description': 'Enable stock adjustment operations', 'order': 1},
                    {'key': 'stock_transfers', 'name': 'Stock Transfers', 'description': 'Enable stock transfer between locations', 'order': 2},
                    {'key': 'low_stock_alerts', 'name': 'Low Stock Alerts', 'description': 'Enable low stock alerts', 'order': 3},
                    {'key': 'reorder_points', 'name': 'Reorder Points', 'description': 'Enable reorder point management', 'order': 4},
                    {'key': 'inventory_reports', 'name': 'Inventory Reports', 'description': 'Enable inventory reports', 'order': 5},
                ]
            },
            {
                'module_name': 'barcodes',
                'description': 'Barcode and QR code generation',
                'is_enabled': True,
                'features': [
                    {'key': 'barcode_generation', 'name': 'Barcode Generation', 'description': 'Enable barcode generation', 'order': 1},
                    {'key': 'qr_generation', 'name': 'QR Code Generation', 'description': 'Enable QR code generation', 'order': 2},
                    {'key': 'label_printing', 'name': 'Label Printing', 'description': 'Enable label printing', 'order': 3},
                    {'key': 'bulk_generation', 'name': 'Bulk Generation', 'description': 'Enable bulk barcode/QR generation', 'order': 4},
                ]
            },
            {
                'module_name': 'expenses',
                'description': 'Expense management module',
                'is_enabled': True,
                'features': []
            },
            {
                'module_name': 'income',
                'description': 'Income management module',
                'is_enabled': True,
                'features': []
            },
            {
                'module_name': 'bank_accounts',
                'description': 'Bank accounts management',
                'is_enabled': True,
                'features': []
            },
            {
                'module_name': 'money_transfer',
                'description': 'Money transfer between accounts',
                'is_enabled': True,
                'features': []
            },
            {
                'module_name': 'balance_sheet',
                'description': 'Balance sheet report',
                'is_enabled': True,
                'features': []
            },
            {
                'module_name': 'trial_balance',
                'description': 'Trial balance report',
                'is_enabled': True,
                'features': []
            },
            {
                'module_name': 'cash_flow',
                'description': 'Cash flow statement',
                'is_enabled': True,
                'features': []
            },
            {
                'module_name': 'account_statement',
                'description': 'Bank account statement',
                'is_enabled': True,
                'features': []
            },
            {
                'module_name': 'reports',
                'description': 'Business reports',
                'is_enabled': True,
                'features': [
                    {'key': 'sales_reports', 'name': 'Sales Reports', 'description': 'Enable sales reports', 'order': 1},
                    {'key': 'product_reports', 'name': 'Product Reports', 'description': 'Enable product reports', 'order': 2},
                    {'key': 'inventory_reports', 'name': 'Inventory Reports', 'description': 'Enable inventory reports', 'order': 3},
                    {'key': 'financial_reports', 'name': 'Financial Reports', 'description': 'Enable financial reports', 'order': 4},
                ]
            },
            {
                'module_name': 'accounting',
                'description': 'Accounting and financial reports',
                'is_enabled': True,
                'features': [
                    {'key': 'chart_of_accounts', 'name': 'Chart of Accounts', 'description': 'Enable chart of accounts', 'order': 1},
                    {'key': 'journal_entries', 'name': 'Journal Entries', 'description': 'Enable journal entries', 'order': 2},
                    {'key': 'balance_sheet', 'name': 'Balance Sheet', 'description': 'Enable balance sheet reports', 'order': 3},
                    {'key': 'income_statement', 'name': 'Income Statement', 'description': 'Enable income statement reports', 'order': 4},
                    {'key': 'trial_balance', 'name': 'Trial Balance', 'description': 'Enable trial balance reports', 'order': 5},
                    {'key': 'general_ledger', 'name': 'General Ledger', 'description': 'Enable general ledger', 'order': 6},
                ]
            },
            {
                'module_name': 'stock',
                'description': 'Stock management and operations',
                'is_enabled': True,
                'features': [
                    {'key': 'manage_stock', 'name': 'Manage Stock', 'description': 'Enable stock management operations', 'order': 1},
                    {'key': 'stock_adjustments', 'name': 'Stock Adjustments', 'description': 'Enable stock adjustment operations', 'order': 2},
                    {'key': 'stock_transfers', 'name': 'Stock Transfers', 'description': 'Enable stock transfer between locations', 'order': 3},
                    {'key': 'stock_reports', 'name': 'Stock Reports', 'description': 'Enable stock-related reports', 'order': 4},
                    {'key': 'low_stock_alerts', 'name': 'Low Stock Alerts', 'description': 'Enable low stock alerts', 'order': 5},
                ]
            },
            {
                'module_name': 'settings',
                'description': 'System settings and configuration',
                'is_enabled': True,
                'features': [
                    {'key': 'user_management', 'name': 'User Management', 'description': 'Enable user management operations', 'order': 1},
                    {'key': 'role_management', 'name': 'Role Management', 'description': 'Enable role management operations', 'order': 2},
                    {'key': 'permission_management', 'name': 'Permission Management', 'description': 'Enable permission management operations', 'order': 3},
                    {'key': 'module_settings', 'name': 'Module Settings', 'description': 'Enable module settings configuration', 'order': 4},
                    {'key': 'system_configuration', 'name': 'System Configuration', 'description': 'Enable system-wide configuration', 'order': 5},
                    {'key': 'multi_branch_support', 'name': 'Multi-Branch Support', 'description': 'Enable multi-branch functionality (branches are optional)', 'order': 6, 'is_enabled': False},  # Disabled by default
                ]
            },
        ]
        
        for module_config in modules_config:
            module, created = ModuleSettings.objects.get_or_create(
                module_name=module_config['module_name'],
                defaults={
                    'description': module_config['description'],
                    'is_enabled': module_config['is_enabled'],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created module: {module.module_name}'))
            else:
                # Update description if changed
                if module.description != module_config['description']:
                    module.description = module_config['description']
                    module.save()
                self.stdout.write(f'Module already exists: {module.module_name}')
            
            # Create features for this module
            features = module_config.get('features', [])
            for feature_config in features:
                feature, feature_created = ModuleFeature.objects.get_or_create(
                    module=module,
                    feature_key=feature_config['key'],
                    defaults={
                        'feature_name': feature_config['name'],
                        'description': feature_config.get('description', ''),
                        'is_enabled': feature_config.get('is_enabled', True),  # Allow setting default enabled state
                        'display_order': feature_config.get('order', 0),
                    }
                )
                if feature_created:
                    self.stdout.write(self.style.SUCCESS(f'  Created feature: {feature.feature_name}'))
                else:
                    # Update if changed
                    updated = False
                    if feature.feature_name != feature_config['name']:
                        feature.feature_name = feature_config['name']
                        updated = True
                    if feature.description != feature_config.get('description', ''):
                        feature.description = feature_config.get('description', '')
                        updated = True
                    if feature.display_order != feature_config.get('order', 0):
                        feature.display_order = feature_config.get('order', 0)
                        updated = True
                    if updated:
                        feature.save()
        
        self.stdout.write(self.style.SUCCESS('\nModule settings and features initialized successfully!'))
