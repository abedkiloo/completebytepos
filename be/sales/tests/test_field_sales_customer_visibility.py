"""Field Sales may only see customers they onboarded (created_by)."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.role_definitions import (
    ROLE_FIELD_AGENT,
    ROLE_MANAGER,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from sales.models import Customer
from sales.visibility import (
    apply_customer_visibility,
    is_field_sales_user,
    user_limited_to_own_customers,
    user_sees_all_customers,
    user_sees_all_debt,
)
from utils.tests.api_test_base import SuperAdminAPITestCase


class FieldSalesCustomerVisibilityTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        roles = sync_default_roles(created_by=self.admin)
        self.field_role = roles[ROLE_FIELD_AGENT]
        self.manager_role = roles[ROLE_MANAGER]
        self.sales_role = roles[ROLE_SALES]

        self.agent = User.objects.create_user(
            username='fs_agent',
            email='fs.agent@example.com',
            password='x',
            first_name='Ann',
            last_name='Agent',
        )
        UserProfile.objects.create(
            user=self.agent,
            role='cashier',
            custom_role=self.field_role,
            is_active=True,
        )
        self.other_agent = User.objects.create_user(
            username='fs_other',
            email='fs.other@example.com',
            password='x',
        )
        UserProfile.objects.create(
            user=self.other_agent,
            role='cashier',
            custom_role=self.field_role,
            is_active=True,
        )
        self.shop_sales = User.objects.create_user(
            username='fs_shop',
            email='fs.shop@example.com',
            password='x',
        )
        UserProfile.objects.create(
            user=self.shop_sales,
            role='cashier',
            custom_role=self.sales_role,
            is_active=True,
        )
        self.manager = User.objects.create_user(
            username='fs_mgr',
            email='fs.mgr@example.com',
            password='x',
        )
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=self.manager_role,
            is_active=True,
        )

        self.mine = Customer.objects.create(
            name='My Duka',
            phone='0711000001',
            is_active=True,
            created_by=self.agent,
        )
        self.theirs = Customer.objects.create(
            name='Other Duka',
            phone='0711000002',
            is_active=True,
            created_by=self.other_agent,
        )
        self.orphan = Customer.objects.create(
            name='Shop Walk-in',
            phone='0711000003',
            is_active=True,
            created_by=self.manager,
        )

    def test_flags(self):
        self.assertTrue(is_field_sales_user(self.agent))
        self.assertTrue(user_limited_to_own_customers(self.agent))
        self.assertFalse(user_sees_all_customers(self.agent))
        self.assertFalse(user_sees_all_debt(self.agent))
        self.assertFalse(user_limited_to_own_customers(self.shop_sales))
        self.assertTrue(user_sees_all_customers(self.manager))
        self.assertFalse(user_limited_to_own_customers(self.manager))

    def test_apply_visibility_queryset(self):
        qs = apply_customer_visibility(Customer.objects.all(), self.agent)
        ids = set(qs.values_list('id', flat=True))
        self.assertEqual(ids, {self.mine.id})

        shop_ids = set(
            apply_customer_visibility(Customer.objects.all(), self.shop_sales).values_list(
                'id', flat=True
            )
        )
        self.assertTrue({self.mine.id, self.theirs.id, self.orphan.id}.issubset(shop_ids))

    def test_list_api_scoped(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        res = client.get('/api/sales/customers/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rows = res.data.get('results', res.data)
        ids = {row['id'] for row in rows}
        self.assertEqual(ids, {self.mine.id})

    def test_detail_other_customer_404(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        res = client.get(f'/api/sales/customers/{self.theirs.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_sees_all(self):
        client = APIClient()
        client.force_authenticate(user=self.manager)
        res = client.get('/api/sales/customers/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rows = res.data.get('results', res.data)
        ids = {row['id'] for row in rows}
        self.assertTrue({self.mine.id, self.theirs.id, self.orphan.id}.issubset(ids))

    def test_debtors_board_forbidden_without_debt_perm(self):
        """Field Sales locked pack has no debt_management — debt board is closed."""
        self.mine.wallet_balance = Decimal('-50.00')
        self.mine.save(update_fields=['wallet_balance'])
        client = APIClient()
        client.force_authenticate(user=self.agent)
        res = client.get('/api/sales/customers/debtors/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
