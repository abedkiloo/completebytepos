"""Shared API test setup for manager / sales personas."""

from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from settings.models import Branch, ModuleSettings, Tenant
from settings.models import StoreSettings


def _enable_modules(*names):
    for name in names:
        ModuleSettings.objects.update_or_create(
            module_name=name,
            defaults={'description': name, 'is_enabled': True},
        )


class ManagerAPITestCase(APITestCase):
    """Authenticated client with Manager role + inventory/reports modules on."""

    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.manager_user = User.objects.create_user(
            username='phase2_manager',
            password='mgr123',
        )
        cls.manager_role = Role.objects.get(name=ROLE_MANAGER)
        UserProfile.objects.create(
            user=cls.manager_user,
            role='manager',
            custom_role=cls.manager_role,
            is_active=True,
        )
        _enable_modules(
            'inventory', 'reports', 'products', 'sales', 'expenses', 'income',
            'bank_accounts', 'money_transfer', 'suppliers', 'accounting', 'pos',
        )
        # Ensure maker-checker is off by default during API tests to avoid
        # cross-test leakage when individual tests enable it.
        store = StoreSettings.load()
        if store.maker_checker_enabled:
            store.maker_checker_enabled = False
            store.save(update_fields=['maker_checker_enabled'])

    def setUp(self):
        token = RefreshToken.for_user(self.manager_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def set_session_branch(self, tenant, branch):
        """Pin tenant/branch on the APIClient session (multi-branch flows)."""
        session = self.client.session
        session['current_tenant_id'] = tenant.id
        session['current_branch_id'] = branch.id
        session.save()

    @staticmethod
    def create_tenant_with_branches(owner, code='TST', branch_names=('HQ', 'Store B')):
        tenant = Tenant.objects.create(
            name=f'{code} Tenant',
            code=code,
            country='Kenya',
            owner=owner,
            created_by=owner,
        )
        branches = []
        for i, name in enumerate(branch_names):
            branches.append(
                Branch.objects.create(
                    tenant=tenant,
                    branch_code=f'{code}-B{i + 1}',
                    name=name,
                    city='Nairobi',
                    country='Kenya',
                    is_active=True,
                    is_headquarters=(i == 0),
                    created_by=owner,
                )
            )
        return tenant, branches[0], branches[1] if len(branches) > 1 else branches[0]


class SalesAPITestCase(APITestCase):
    """Sales personnel — POS access, no reports."""

    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.sales_user = User.objects.create_user(
            username='phase2_sales',
            password='sales123',
        )
        cls.sales_role = Role.objects.get(name=ROLE_SALES)
        UserProfile.objects.create(
            user=cls.sales_user,
            role='cashier',
            custom_role=cls.sales_role,
            is_active=True,
        )
        _enable_modules('inventory', 'reports', 'products', 'sales', 'pos')

    def setUp(self):
        token = RefreshToken.for_user(self.sales_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')


class SuperAdminAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.admin = User.objects.create_superuser(
            username='phase2_admin',
            email='admin@test.com',
            password='admin123',
        )
        role = Role.objects.get(name=ROLE_SUPER_ADMIN)
        profile, _ = UserProfile.objects.get_or_create(
            user=cls.admin,
            defaults={'role': 'super_admin', 'custom_role': role, 'is_active': True},
        )
        profile.role = 'super_admin'
        profile.custom_role = role
        profile.is_active = True
        profile.save()
        _enable_modules('inventory', 'reports', 'products', 'sales')
        # Ensure maker-checker is off by default for super-admin API tests as well
        store = StoreSettings.load()
        if store.maker_checker_enabled:
            store.maker_checker_enabled = False
            store.save(update_fields=['maker_checker_enabled'])

    def setUp(self):
        token = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
