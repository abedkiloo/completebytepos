"""
Initialize all permissions for the system
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from accounts.models import Permission, Role, UserProfile


class Command(BaseCommand):
    help = 'Initialize all permissions and default roles'

    def handle(self, *args, **options):
        self.stdout.write('Initializing permissions...')
        
        # Define all permissions
        permissions_data = [
            # Products
            ('products', 'view', 'View products'),
            ('products', 'create', 'Create products'),
            ('products', 'update', 'Update products'),
            ('products', 'delete', 'Delete products'),
            ('products', 'export', 'Export products'),
            ('products', 'import', 'Import products'),
            
            # Categories
            ('categories', 'view', 'View categories'),
            ('categories', 'create', 'Create categories'),
            ('categories', 'update', 'Update categories'),
            ('categories', 'delete', 'Delete categories'),
            
            # Inventory
            ('inventory', 'view', 'View inventory'),
            ('inventory', 'create', 'Create inventory movements'),
            ('inventory', 'update', 'Update inventory'),
            ('inventory', 'delete', 'Delete inventory movements'),
            ('inventory', 'manage', 'Manage inventory settings'),
            
            # Sales
            ('sales', 'view', 'View sales'),
            ('sales', 'create', 'Create sales'),
            ('sales', 'update', 'Update sales'),
            ('sales', 'delete', 'Delete sales'),
            ('sales', 'export', 'Export sales'),
            
            # POS
            ('pos', 'view', 'Access POS'),
            ('pos', 'create', 'Create sales via POS'),
            
            # Barcodes
            ('barcodes', 'view', 'View barcodes'),
            ('barcodes', 'create', 'Generate barcodes'),
            ('barcodes', 'export', 'Export barcodes'),
            
            # Reports
            ('reports', 'view', 'View reports'),
            ('reports', 'export', 'Export reports'),
            
            # Expenses
            ('expenses', 'view', 'View expenses'),
            ('expenses', 'create', 'Create expenses'),
            ('expenses', 'update', 'Update expenses'),
            ('expenses', 'delete', 'Delete expenses'),
            ('expenses', 'approve', 'Approve expenses'),
            ('expenses', 'export', 'Export expenses'),
            
            # Income
            ('income', 'view', 'View income'),
            ('income', 'create', 'Create income'),
            ('income', 'update', 'Update income'),
            ('income', 'delete', 'Delete income'),
            ('income', 'approve', 'Approve income'),
            ('income', 'export', 'Export income'),
            
            # Bank Accounts
            ('bank_accounts', 'view', 'View bank accounts'),
            ('bank_accounts', 'create', 'Create bank accounts'),
            ('bank_accounts', 'update', 'Update bank accounts'),
            ('bank_accounts', 'delete', 'Delete bank accounts'),
            ('bank_accounts', 'manage', 'Manage bank accounts'),
            
            # Money Transfer
            ('money_transfer', 'view', 'View money transfers'),
            ('money_transfer', 'create', 'Create money transfers'),
            ('money_transfer', 'approve', 'Approve money transfers'),
            
            # Accounting
            ('accounting', 'view', 'View accounting'),
            ('accounting', 'create', 'Create journal entries'),
            ('accounting', 'update', 'Update accounting'),
            ('accounting', 'export', 'Export accounting reports'),
            
            # User Management
            ('users', 'view', 'View users'),
            ('users', 'create', 'Create users'),
            ('users', 'update', 'Update users'),
            ('users', 'delete', 'Delete users'),
            ('users', 'manage', 'Manage users'),
            
            # Role Management
            ('roles', 'view', 'View roles'),
            ('roles', 'create', 'Create roles'),
            ('roles', 'update', 'Update roles'),
            ('roles', 'delete', 'Delete roles'),
            ('roles', 'manage', 'Manage roles'),
            
            # Settings
            ('settings', 'view', 'View settings'),
            ('settings', 'update', 'Update settings'),
            ('settings', 'manage', 'Manage settings'),
            
            # Module Settings
            ('modules', 'view', 'View module settings'),
            ('modules', 'update', 'Update module settings'),
            ('modules', 'manage', 'Manage module settings'),
        ]
        
        # Create permissions
        created_count = 0
        for module, action, description in permissions_data:
            permission, created = Permission.objects.get_or_create(
                module=module,
                action=action,
                defaults={
                    'name': f'{module}.{action}',
                    'description': description
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created permission: {permission.name}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nCreated {created_count} new permissions'))
        
        # Create default roles
        self.stdout.write('\nCreating default roles...')
        
        # Super Admin Role (all permissions)
        super_admin_role, created = Role.objects.get_or_create(
            name='Super Admin',
            defaults={
                'description': 'Full system access with all permissions',
                'is_system_role': True,
                'is_active': True
            }
        )
        if created:
            super_admin_role.permissions.set(Permission.objects.all())
            self.stdout.write(self.style.SUCCESS('Created Super Admin role with all permissions'))
        
        # Admin Role (most permissions except super admin only)
        admin_role, created = Role.objects.get_or_create(
            name='Admin',
            defaults={
                'description': 'Administrative access to most modules',
                'is_system_role': True,
                'is_active': True
            }
        )
        if created:
            admin_permissions = Permission.objects.exclude(
                module__in=['users', 'roles', 'settings', 'modules']
            ).exclude(
                Q(module='users', action='delete') |
                Q(module='roles', action__in=['create', 'update', 'delete']) |
                Q(module='settings', action__in=['update', 'manage']) |
                Q(module='modules', action__in=['update', 'manage'])
            )
            admin_role.permissions.set(admin_permissions)
            self.stdout.write(self.style.SUCCESS('Created Admin role'))
        
        # Manager Role
        manager_role, created = Role.objects.get_or_create(
            name='Manager',
            defaults={
                'description': 'Management access to operations',
                'is_system_role': True,
                'is_active': True
            }
        )
        if created:
            manager_permissions = Permission.objects.filter(
                module__in=['products', 'categories', 'inventory', 'sales', 'pos', 
                           'barcodes', 'reports', 'expenses', 'income']
            ).exclude(action='delete')
            manager_role.permissions.set(manager_permissions)
            self.stdout.write(self.style.SUCCESS('Created Manager role'))
        
        # Cashier Role
        cashier_role, created = Role.objects.get_or_create(
            name='Cashier',
            defaults={
                'description': 'Basic access for sales operations',
                'is_system_role': True,
                'is_active': True
            }
        )
        if created:
            cashier_permissions = Permission.objects.filter(
                module__in=['products', 'categories', 'sales', 'pos', 'barcodes']
            ).filter(action__in=['view', 'create'])
            cashier_role.permissions.set(cashier_permissions)
            self.stdout.write(self.style.SUCCESS('Created Cashier role'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ Permissions and roles initialized successfully!'))

