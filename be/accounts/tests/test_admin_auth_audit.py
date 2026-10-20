"""Admin helpers, auth endpoints, audit filters, and sensitive_edits coverage."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.admin import PermissionAdmin, RoleAdmin, UserAdmin, UserProfileInline
from accounts.models import AuditLog, Permission, Role, UserProfile
from accounts.role_definitions import ensure_permissions, sync_default_roles
from accounts.sensitive_edits import (
    clamp_holding_financial_adjustments,
    sales_catalog_mode_active,
    strip_sensitive_product_fields,
    validate_sale_unit_price_override,
)
from settings.admin import BranchAdmin, ModuleFeatureAdmin, ModuleSettingsAdmin
from settings.models import Branch, ModuleFeature, ModuleSettings, Tenant
from utils.tests.api_test_base import SuperAdminAPITestCase


class AccountsAdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser('adm', 'a@t.com', 'x')
        ensure_permissions()
        sync_default_roles()
        self.role = Role.objects.create(name='AdminTestRole', description='t')

    def test_user_admin_inline_only_for_existing(self):
        admin = UserAdmin(User, self.site)
        request = self.factory.get('/')
        request.user = self.user
        self.assertEqual(admin.get_inline_instances(request, obj=None), [])
        self.assertTrue(admin.get_inline_instances(request, obj=self.user))

    def test_role_admin_methods(self):
        admin = RoleAdmin(Role, self.site)
        request = self.factory.get('/')
        request.user = self.user
        self.assertEqual(admin.permissions_count(self.role), 0)
        self.assertEqual(admin.users_count(self.role), 0)
        admin.save_model(request, self.role, form=None, change=False)
        self.assertEqual(self.role.created_by, self.user)
        self.role.is_system_role = True
        self.role.save()
        self.assertFalse(admin.has_delete_permission(request, self.role))
        self.assertTrue(admin.has_delete_permission(request, None))


class SettingsAdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser('sadm', 's@t.com', 'x')
        UserProfile.objects.create(user=self.user, role='super_admin', is_active=True)
        self.module = ModuleSettings.objects.create(
            module_name='products',
            description='P',
            is_enabled=True,
        )
        self.feature = ModuleFeature.objects.create(
            module=self.module,
            feature_key='product_images',
            feature_name='Images',
            is_enabled=True,
            display_order=1,
        )
        self.tenant = Tenant.objects.create(
            name='AdmT',
            code='ADMT',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
        )
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            branch_code='A1',
            name='A1',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            created_by=self.user,
        )

    def test_module_settings_admin(self):
        admin = ModuleSettingsAdmin(ModuleSettings, self.site)
        request = self.factory.get('/')
        request.user = self.user
        self.assertEqual(admin.features_count(self.module), 1)
        admin.save_model(request, self.module, form=None, change=True)
        self.assertEqual(self.module.updated_by, self.user)
        self.assertTrue(admin.has_add_permission(request))
        self.assertTrue(admin.has_change_permission(request))
        self.assertTrue(admin.has_delete_permission(request))

    def test_module_feature_and_branch_admin(self):
        request = self.factory.get('/')
        request.user = self.user
        fadmin = ModuleFeatureAdmin(ModuleFeature, self.site)
        fadmin.save_model(request, self.feature, form=None, change=True)
        self.assertEqual(self.feature.updated_by, self.user)
        self.assertTrue(fadmin.has_add_permission(request))
        self.assertTrue(fadmin.has_change_permission(request))
        self.assertTrue(fadmin.has_delete_permission(request))

        badmin = BranchAdmin(Branch, self.site)
        new_branch = Branch(
            tenant=self.tenant,
            branch_code='A2',
            name='A2',
            city='Nairobi',
            country='Kenya',
            is_active=True,
        )
        badmin.save_model(request, new_branch, form=None, change=False)
        self.assertEqual(new_branch.created_by, self.user)


class AuthSearchAuditAPITests(SuperAdminAPITestCase):
    def test_login_logout_me_search(self):
        self.client.credentials()
        response = self.client.post(
            '/api/accounts/auth/login/',
            {'username': 'phase2_admin', 'password': 'admin123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        refresh = response.data['refresh']
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        response = self.client.get('/api/accounts/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/accounts/users/search/', {'q': 'phase2'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get('/api/accounts/users/search/', {'q': ''})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(
            '/api/accounts/users/search/',
            {'q': 'phase2', 'limit': 'bad'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(
            '/api/accounts/users/search/',
            {'q': 'phase2', 'limit': '0'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(
            '/api/accounts/users/search/',
            {'q': 'phase2', 'limit': '5000'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            '/api/accounts/auth/logout/',
            {'refresh': refresh},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_failure_with_origin(self):
        self.client.credentials()
        response = self.client.post(
            '/api/accounts/auth/login/',
            {'username': 'phase2_admin', 'password': 'wrong'},
            format='json',
            HTTP_ORIGIN='http://localhost:3000',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_audit_log_filters(self):
        AuditLog.objects.create(
            user=self.admin,
            username_snapshot='phase2_admin',
            action=AuditLog.ACTION_LOGIN,
            module='users',
            object_type='auth.User',
            object_repr='phase2_admin',
            path='/api/accounts/auth/login/',
        )
        with patch('accounts.sensitive_edits.user_may_view_audit_log', return_value=True):
            response = self.client.get(
                '/api/accounts/audit-logs/',
                {
                    'user': self.admin.pk,
                    'action': AuditLog.ACTION_LOGIN,
                    'module': 'users',
                    'object_type': 'auth.User',
                    'date_from': '2000-01-01',
                    'date_to': '2099-01-01',
                    'q': 'phase2',
                },
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SensitiveEditsUnitTests(TestCase):
    def test_sales_catalog_mode_and_strip(self):
        user = User.objects.create_user('sens', password='x')
        with patch(
            'products.catalog_access.user_may_edit_product_pricing',
            return_value=False,
        ), patch(
            'products.catalog_access.user_may_edit_catalog_details',
            return_value=True,
        ), patch(
            'products.catalog_access.products_sales_catalog_access_enabled',
            return_value=True,
        ):
            self.assertTrue(sales_catalog_mode_active(user))
        with patch(
            'products.catalog_access.user_may_edit_product_pricing',
            return_value=True,
        ):
            self.assertFalse(sales_catalog_mode_active(user))

        with patch(
            'products.catalog_access.strip_product_fields_by_access',
            return_value={'name': 'x'},
        ) as mock_strip:
            out = strip_sensitive_product_fields({'price': 1}, user=user)
            self.assertEqual(out, {'name': 'x'})
            mock_strip.assert_called_once()

    def test_validate_sale_unit_price_override(self):
        user = User.objects.create_user('price_u', password='x')
        product = MagicMock()
        validate_sale_unit_price_override(
            user, product=product, variant=None, override=None
        )
        with patch('products.stock_utils.sellable_unit_price', return_value=Decimal('10')):
            validate_sale_unit_price_override(
                user, product=product, variant=None, override=Decimal('12')
            )
            with self.assertRaises(ValidationError):
                validate_sale_unit_price_override(
                    user, product=product, variant=None, override=Decimal('5')
                )
            with self.assertRaises(ValidationError):
                validate_sale_unit_price_override(
                    user, product=product, variant=None, override=Decimal('-1')
                )
            with self.assertRaises(ValidationError):
                validate_sale_unit_price_override(
                    user, product=product, variant=None, override='not-a-number'
                )

    def test_clamp_holding(self):
        user = User.objects.create_user('clamp_u', password='x')
        with patch(
            'accounts.sensitive_edits.user_may_edit_financial_fields',
            return_value=True,
        ):
            self.assertEqual(
                clamp_holding_financial_adjustments(user, Decimal('1'), Decimal('2')),
                (Decimal('1'), Decimal('2')),
            )
        with patch(
            'accounts.sensitive_edits.user_may_edit_financial_fields',
            return_value=False,
        ):
            self.assertEqual(
                clamp_holding_financial_adjustments(user, Decimal('1'), Decimal('2')),
                (Decimal('0'), Decimal('0')),
            )
