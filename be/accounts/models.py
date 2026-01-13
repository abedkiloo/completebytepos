from django.db import models
from django.contrib.auth.models import User


class Permission(models.Model):
    """Granular permissions for modules and actions"""
    MODULE_CHOICES = [
        ('products', 'Products'),
        ('categories', 'Categories'),
        ('inventory', 'Inventory'),
        ('sales', 'Sales'),
        ('pos', 'Point of Sale'),
        ('barcodes', 'Barcodes'),
        ('reports', 'Reports'),
        ('expenses', 'Expenses'),
        ('income', 'Income'),
        ('bank_accounts', 'Bank Accounts'),
        ('money_transfer', 'Money Transfer'),
        ('accounting', 'Accounting'),
        ('users', 'User Management'),
        ('roles', 'Role Management'),
        ('settings', 'System Settings'),
        ('modules', 'Module Settings'),
    ]
    
    ACTION_CHOICES = [
        ('view', 'View'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('manage', 'Manage'),  # Full management access
    ]

    module = models.CharField(max_length=50, choices=MODULE_CHOICES)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    name = models.CharField(max_length=100, unique=True, help_text='Unique permission name (e.g., products.view)')
    description = models.TextField(blank=True, help_text='Permission description')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['module', 'action']]
        ordering = ['module', 'action']
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"

    def __str__(self):
        return f"{self.get_module_display()}.{self.get_action_display()}"

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"{self.module}.{self.action}"
        super().save(*args, **kwargs)


class Role(models.Model):
    """Roles that can be assigned to users with specific permissions"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, related_name='roles', blank=True)
    is_system_role = models.BooleanField(default=False, help_text='System roles cannot be deleted')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles_created'
    )

    class Meta:
        ordering = ['name']
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name

    def has_permission(self, module, action):
        """Check if role has a specific permission"""
        return self.permissions.filter(module=module, action=action).exists()

    def has_module_access(self, module):
        """Check if role has any access to a module"""
        return self.permissions.filter(module=module).exists()


class UserProfile(models.Model):
    """Extended user profile with role-based access"""
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('cashier', 'Cashier'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cashier', help_text='Legacy role field')
    custom_role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text='Custom role with specific permissions'
    )
    phone_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True, help_text='User account status')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users_created'
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        role_name = self.custom_role.name if self.custom_role else self.get_role_display()
        return f"{self.user.username} - {role_name}"

    @property
    def is_super_admin(self):
        """Check if user is super admin"""
        return self.role == 'super_admin' or self.user.is_superuser

    @property
    def is_admin(self):
        """Check if user is admin"""
        return self.role in ['super_admin', 'admin'] or self.user.is_staff

    @property
    def is_manager(self):
        """Check if user is manager"""
        return self.role in ['super_admin', 'admin', 'manager']

    def has_permission(self, module, action):
        """Check if user has a specific permission"""
        # Super admin has all permissions
        if self.is_super_admin:
            return True
        
        # Check custom role permissions
        if self.custom_role and self.custom_role.is_active:
            return self.custom_role.has_permission(module, action)
        
        # Check legacy role permissions
        if self.role == 'admin':
            # Admins have most permissions except super admin only
            if module in ['users', 'roles', 'settings', 'modules']:
                return action in ['view', 'manage']
            return True
        
        if self.role == 'manager':
            # Managers can view and manage most things except users/roles/settings
            if module in ['users', 'roles', 'settings', 'modules']:
                return False
            return action in ['view', 'create', 'update', 'export', 'import']
        
        if self.role == 'cashier':
            # Cashiers have limited permissions
            allowed_modules = ['products', 'categories', 'sales', 'pos', 'barcodes']
            if module not in allowed_modules:
                return False
            if module == 'sales' or module == 'pos':
                return action in ['view', 'create']
            return action == 'view'
        
        return False

    def has_module_access(self, module):
        """Check if user has any access to a module"""
        if self.is_super_admin:
            return True
        
        if self.custom_role and self.custom_role.is_active:
            return self.custom_role.has_module_access(module)
        
        # Legacy role checks
        if self.role == 'admin':
            return True
        
        if self.role == 'manager':
            return module not in ['users', 'roles', 'settings', 'modules']
        
        if self.role == 'cashier':
            return module in ['products', 'categories', 'sales', 'pos', 'barcodes']
        
        return False

    def get_all_permissions(self):
        """Get all permissions for this user"""
        if self.is_super_admin:
            # Return all permissions
            return Permission.objects.all()
        
        if self.custom_role and self.custom_role.is_active:
            return self.custom_role.permissions.all()
        
        # For legacy roles, return empty (permissions checked via has_permission)
        return Permission.objects.none()


# Module settings models moved to settings app
# Import for backward compatibility - allows existing code to continue working
from settings.models import ModuleSettings, ModuleFeature
