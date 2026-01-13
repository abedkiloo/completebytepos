from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile, Role, Permission


class Command(BaseCommand):
    help = 'Create superuser and admin users with proper profiles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--superuser-username',
            type=str,
            default='admin',
            help='Username for superuser (default: admin)',
        )
        parser.add_argument(
            '--superuser-password',
            type=str,
            default='admin123',
            help='Password for superuser (default: admin123)',
        )
        parser.add_argument(
            '--superuser-email',
            type=str,
            default='admin@example.com',
            help='Email for superuser (default: admin@example.com)',
        )
        parser.add_argument(
            '--admin-username',
            type=str,
            default='manager',
            help='Username for admin user (default: manager)',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='manager123',
            help='Password for admin user (default: manager123)',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='manager@example.com',
            help='Email for admin user (default: manager@example.com)',
        )

    def handle(self, *args, **options):
        # Create or update superuser
        superuser_username = options['superuser_username']
        superuser_password = options['superuser_password']
        superuser_email = options['superuser_email']
        
        superuser, created = User.objects.get_or_create(
            username=superuser_username,
            defaults={
                'email': superuser_email,
                'is_superuser': True,
                'is_staff': True,
                'is_active': True,
            }
        )
        
        if created:
            superuser.set_password(superuser_password)
            superuser.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Created superuser: {superuser_username}'))
        else:
            # Update existing superuser
            superuser.is_superuser = True
            superuser.is_staff = True
            superuser.is_active = True
            superuser.email = superuser_email
            superuser.set_password(superuser_password)
            superuser.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Updated superuser: {superuser_username}'))
        
        # Create or update superuser profile
        superuser_profile, created = UserProfile.objects.get_or_create(
            user=superuser,
            defaults={
                'role': 'super_admin',
                'is_active': True,
            }
        )
        
        if not created:
            superuser_profile.role = 'super_admin'
            superuser_profile.is_active = True
            superuser_profile.save()
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Superuser profile created/updated'))
        
        # Create or update admin user
        admin_username = options['admin_username']
        admin_password = options['admin_password']
        admin_email = options['admin_email']
        
        admin_user, created = User.objects.get_or_create(
            username=admin_username,
            defaults={
                'email': admin_email,
                'is_superuser': False,
                'is_staff': True,  # Admin can access Django admin
                'is_active': True,
            }
        )
        
        if created:
            admin_user.set_password(admin_password)
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Created admin user: {admin_username}'))
        else:
            # Update existing admin user
            admin_user.is_superuser = False
            admin_user.is_staff = True
            admin_user.is_active = True
            admin_user.email = admin_email
            admin_user.set_password(admin_password)
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Updated admin user: {admin_username}'))
        
        # Create or update admin profile
        admin_profile, created = UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={
                'role': 'admin',
                'is_active': True,
                'created_by': superuser,
            }
        )
        
        if not created:
            admin_profile.role = 'admin'
            admin_profile.is_active = True
            if not admin_profile.created_by:
                admin_profile.created_by = superuser
            admin_profile.save()
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Admin profile created/updated'))
        
        # Create default permissions if they don't exist
        self.stdout.write('Creating default permissions...')
        modules = [
            'products', 'categories', 'inventory', 'sales', 'pos', 'barcodes',
            'reports', 'expenses', 'income', 'bank_accounts', 'money_transfer',
            'accounting', 'users', 'roles', 'settings', 'modules'
        ]
        actions = ['view', 'create', 'update', 'delete', 'approve', 'export', 'import', 'manage']
        
        permissions_created = 0
        for module in modules:
            for action in actions:
                perm, created = Permission.objects.get_or_create(
                    module=module,
                    action=action,
                    defaults={
                        'description': f'Permission to {action} {module}',
                    }
                )
                if created:
                    permissions_created += 1
        
        if permissions_created > 0:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created {permissions_created} permissions'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  ✓ All permissions already exist'))
        
        # Create default roles if they don't exist
        self.stdout.write('Creating default roles...')
        
        # Admin Role - has most permissions except super admin only
        admin_role, created = Role.objects.get_or_create(
            name='Administrator',
            defaults={
                'description': 'Administrator role with full access except user/role management',
                'is_system_role': True,
                'is_active': True,
                'created_by': superuser,
            }
        )
        
        if not created:
            admin_role.is_active = True
            admin_role.save()
        
        # Assign permissions to admin role (all except users/roles/settings/modules manage)
        admin_permissions = Permission.objects.exclude(
            module__in=['users', 'roles', 'settings', 'modules']
        ).exclude(
            module__in=['users', 'roles', 'settings', 'modules'],
            action='manage'
        )
        admin_role.permissions.set(admin_permissions)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created/updated Administrator role'))
        
        # Manager Role
        manager_role, created = Role.objects.get_or_create(
            name='Manager',
            defaults={
                'description': 'Manager role with view/create/update permissions',
                'is_system_role': True,
                'is_active': True,
                'created_by': superuser,
            }
        )
        
        if not created:
            manager_role.is_active = True
            manager_role.save()
        
        # Manager permissions: view, create, update, export for most modules
        manager_permissions = Permission.objects.exclude(
            module__in=['users', 'roles', 'settings', 'modules']
        ).filter(
            action__in=['view', 'create', 'update', 'export', 'import']
        )
        manager_role.permissions.set(manager_permissions)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created/updated Manager role'))
        
        # Cashier Role
        cashier_role, created = Role.objects.get_or_create(
            name='Cashier',
            defaults={
                'description': 'Cashier role with limited POS and sales permissions',
                'is_system_role': True,
                'is_active': True,
                'created_by': superuser,
            }
        )
        
        if not created:
            cashier_role.is_active = True
            cashier_role.save()
        
        # Cashier permissions: view products, create sales
        cashier_permissions = Permission.objects.filter(
            module__in=['products', 'categories', 'sales', 'pos', 'barcodes']
        ).filter(
            action__in=['view', 'create']
        )
        cashier_role.permissions.set(cashier_permissions)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created/updated Cashier role'))
        
        # Optionally assign admin role to admin user
        if admin_profile.custom_role != admin_role:
            admin_profile.custom_role = admin_role
            admin_profile.save()
            self.stdout.write(self.style.SUCCESS(f'  ✓ Assigned Administrator role to {admin_username}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ User creation complete!\n'
            f'   Superuser: {superuser_username} / {superuser_password}\n'
            f'   Admin: {admin_username} / {admin_password}'
        ))

