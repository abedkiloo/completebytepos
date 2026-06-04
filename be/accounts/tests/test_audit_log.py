"""Audit log writes and read API."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AuditLog, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, sync_default_roles
from products.models import Category, Product
from utils.audit import log_audit, diff_instance
from utils.tests.api_test_base import SuperAdminAPITestCase


class AuditLogHelperTests(TestCase):
    def test_log_audit_creates_row(self):
        user = User.objects.create_user('u1', password='x')
        log_audit(None, AuditLog.ACTION_LOGIN, user, module='users')
        self.assertEqual(AuditLog.objects.filter(action='login').count(), 1)

    def test_diff_instance_detects_change(self):
        cat = Category.objects.create(name='A', is_active=True)
        p1 = Product.objects.create(
            name='P', sku='P-1', category=cat, price=Decimal('10'), is_active=True
        )
        p1.price = Decimal('20')
        diff = diff_instance(
            Product.objects.get(pk=p1.pk),
            p1,
        )
        self.assertIn('price', diff)


class AuditLogAPITests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        AuditLog.objects.create(
            user=self.admin,
            username_snapshot='admin',
            action='checkout',
            module='sales',
            object_repr='SALE-1',
            changes={'total': '100'},
        )

    def test_super_admin_lists_audit_logs(self):
        response = self.client.get('/api/accounts/audit-logs/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data.get('results', response.data)), 1)

    def test_filter_by_action(self):
        response = self.client.get('/api/accounts/audit-logs/', {'action': 'checkout'})
        self.assertEqual(response.status_code, 200)


class AuditLogManagerAccessTests(TestCase):
    def setUp(self):
        sync_default_roles()
        self.client = APIClient()
        self.manager = User.objects.create_user('mgr', password='mgr123')
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
        )
        self.sales = User.objects.create_user('sales', password='sales123')
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )
        AuditLog.objects.create(
            username_snapshot='sales',
            action='login',
            module='users',
            object_repr='login',
        )

    def _auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_manager_can_read_audit_log(self):
        self._auth(self.manager)
        response = self.client.get('/api/accounts/audit-logs/')
        self.assertEqual(response.status_code, 200)

    def test_sales_cannot_read_audit_log(self):
        self._auth(self.sales)
        response = self.client.get('/api/accounts/audit-logs/')
        self.assertEqual(response.status_code, 403)
