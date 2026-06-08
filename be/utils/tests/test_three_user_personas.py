"""
End-to-end API flows for the three bootstrap personas (admin, manager, sales).

Mirrors production users from ``create_users`` / ``role_definitions.py``.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    BOOTSTRAP_USERS,
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from products.models import Category, Product
from settings.test_utils import disable_multi_branch_support
from utils.tests.api_test_base import _enable_modules


def _client_for_user(user):
    client = APITestCase().client_class()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
    return client


class ThreeUserPersonasTestCase(APITestCase):
    """Validate critical paths per bootstrap role."""

    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        _enable_modules(
            'products', 'sales', 'pos', 'inventory', 'reports', 'expenses',
            'income', 'users', 'roles', 'settings', 'modules', 'customers',
        )
        disable_multi_branch_support()
        cls.users = {}
        for spec in BOOTSTRAP_USERS:
            user, _ = User.objects.get_or_create(
                username=spec['username'],
                defaults={
                    'email': spec['email'],
                    'is_superuser': spec['is_superuser'],
                    'is_staff': spec['is_staff'],
                    'is_active': True,
                },
            )
            user.set_password(spec['password'])
            user.save()
            role = Role.objects.get(name=spec['custom_role_name'])
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'role': spec['profile_role'],
                    'custom_role': role,
                    'is_active': True,
                },
            )
            cls.users[spec['username']] = user

        cat = Category.objects.create(name='Persona Cat')
        cls.product = Product.objects.create(
            name='Persona SKU',
            sku='PERSONA-001',
            category=cat,
            price=Decimal('99.00'),
            cost=Decimal('50.00'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )

    def test_admin_can_access_users_and_dashboard(self):
        client = _client_for_user(self.users['admin'])
        self.assertEqual(client.get('/api/reports/dashboard/').status_code, status.HTTP_200_OK)
        self.assertEqual(client.get('/api/accounts/users/').status_code, status.HTTP_200_OK)
        self.assertEqual(client.get('/api/settings/modules/').status_code, status.HTTP_200_OK)

    def test_manager_can_purchase_stock_and_view_reports(self):
        client = _client_for_user(self.users['manager'])
        purchase = client.post(
            '/api/inventory/purchase/',
            {
                'product_id': self.product.id,
                'quantity': 2,
                'unit_cost': '50.00',
            },
            format='json',
        )
        self.assertEqual(purchase.status_code, status.HTTP_201_CREATED, purchase.data)
        self.assertEqual(client.get('/api/reports/sales_overview/').status_code, status.HTTP_200_OK)
        self.assertEqual(client.get('/api/expenses/').status_code, status.HTTP_200_OK)

    def test_manager_cannot_toggle_module_settings(self):
        """Manager lacks settings.manage — only super admin configures modules."""
        client = _client_for_user(self.users['manager'])
        modules = client.get('/api/settings/modules/')
        self.assertEqual(modules.status_code, status.HTTP_200_OK)
        if modules.data:
            first = modules.data[0] if isinstance(modules.data, list) else modules.data.get('results', [{}])[0]
            mod_id = first.get('id')
            if mod_id:
                patch = client.patch(
                    f'/api/settings/modules/{mod_id}/',
                    {'is_enabled': False},
                    format='json',
                )
                self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_can_search_products_and_save_holding_sale(self):
        """Sales can search catalog and save a billing holding draft (no stock move)."""
        client = _client_for_user(self.users['sales'])
        search = client.get('/api/products/search/', {'q': 'Persona'})
        self.assertEqual(search.status_code, status.HTTP_200_OK)
        holding = client.post(
            '/api/sales/holding/',
            {
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '99.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(holding.status_code, status.HTTP_200_OK, holding.data)
        self.assertEqual(holding.data.get('status'), 'holding')

    def test_sales_cannot_access_reports_or_create_users(self):
        client = _client_for_user(self.users['sales'])
        self.assertEqual(client.get('/api/reports/dashboard/').status_code, status.HTTP_403_FORBIDDEN)
        summary = client.get('/api/sales/dashboard-summary/')
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertIn('today', summary.data)
        self.assertNotIn('month', summary.data)
        create_user = client.post(
            '/api/accounts/users/',
            {'username': 'x', 'password': 'x12345', 'email': 'x@t.com'},
            format='json',
        )
        self.assertEqual(create_user.status_code, status.HTTP_403_FORBIDDEN)
        users = client.get('/api/accounts/users/')
        self.assertEqual(users.status_code, status.HTTP_200_OK)
        results = users.data.get('results', users.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['username'], 'sales')

    def test_sales_cannot_delete_products(self):
        client = _client_for_user(self.users['sales'])
        response = client.delete(f'/api/products/{self.product.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_endpoint_returns_role_for_each_persona(self):
        for username, expected_role in (
            ('admin', ROLE_SUPER_ADMIN),
            ('manager', ROLE_MANAGER),
            ('sales', ROLE_SALES),
        ):
            client = _client_for_user(self.users[username])
            me = client.get('/api/accounts/auth/me/')
            self.assertEqual(me.status_code, status.HTTP_200_OK)
            self.assertEqual(me.data['profile']['custom_role']['name'], expected_role)
