"""Sales visibility: own sales by default; admin / manager / sales.view_all see store-wide."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from sales.models import Sale
from sales.services import SaleService
from sales.visibility import user_sees_all_debt, user_sees_all_sales
from sales.views import SaleViewSet


class SalesVisibilityTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('vis_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager,
            role='manager',
            custom_role=roles[ROLE_MANAGER],
            is_active=True,
        )
        cls.admin = User.objects.create_user('vis_admin', password='x')
        UserProfile.objects.create(
            user=cls.admin,
            role='super_admin',
            custom_role=roles[ROLE_SUPER_ADMIN],
            is_active=True,
        )
        cls.sales_a = User.objects.create_user('vis_sales_a', password='x')
        UserProfile.objects.create(
            user=cls.sales_a,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        cls.sales_b = User.objects.create_user('vis_sales_b', password='x')
        UserProfile.objects.create(
            user=cls.sales_b,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        cls.sale_a = Sale.objects.create(
            cashier=cls.sales_a,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            status='completed',
            payment_method='cash',
        )
        cls.sale_b = Sale.objects.create(
            cashier=cls.sales_b,
            subtotal=Decimal('200.00'),
            total=Decimal('200.00'),
            amount_paid=Decimal('200.00'),
            status='completed',
            payment_method='cash',
        )

    def test_user_sees_all_sales_flags(self):
        self.assertTrue(user_sees_all_sales(self.admin))
        self.assertTrue(user_sees_all_sales(self.manager))
        self.assertFalse(user_sees_all_sales(self.sales_a))

    def test_user_sees_all_debt_flags(self):
        self.assertTrue(user_sees_all_debt(self.admin))
        self.assertTrue(user_sees_all_debt(self.manager))
        # Default Sales role can collect debt, so they get the full debtors board.
        self.assertTrue(user_sees_all_debt(self.sales_a))

        view_only = Role.objects.create(name='Debt Viewer Only', is_active=True)
        view_only.permissions.add(
            Permission.objects.get(module='debt_management', action='view')
        )
        viewer = User.objects.create_user('vis_debt_viewer', password='x')
        UserProfile.objects.create(
            user=viewer, role='cashier', custom_role=view_only, is_active=True,
        )
        self.assertFalse(user_sees_all_debt(viewer))

    def test_view_all_permission_grants_storewide(self):
        perm = Permission.objects.get(module='sales', action='view_all')
        role = Role.objects.create(name='Store Viewer', is_active=True)
        role.permissions.add(perm)
        user = User.objects.create_user('vis_viewer', password='x')
        UserProfile.objects.create(
            user=user, role='cashier', custom_role=role, is_active=True,
        )
        self.assertTrue(user_sees_all_sales(user))

    def test_build_queryset_scopes_sales_agent(self):
        factory = RequestFactory()
        req = factory.get('/api/sales/')
        req.user = self.sales_a
        qs = SaleService().build_queryset({}, request=req)
        ids = set(qs.values_list('id', flat=True))
        self.assertIn(self.sale_a.id, ids)
        self.assertNotIn(self.sale_b.id, ids)

    def test_build_queryset_manager_sees_all_sellers(self):
        factory = RequestFactory()
        req = factory.get('/api/sales/')
        req.user = self.manager
        qs = SaleService().build_queryset({}, request=req)
        ids = set(qs.values_list('id', flat=True))
        self.assertIn(self.sale_a.id, ids)
        self.assertIn(self.sale_b.id, ids)

    def test_build_queryset_manager_filters_by_seller(self):
        factory = RequestFactory()
        req = factory.get('/api/sales/')
        req.user = self.manager
        qs = SaleService().build_queryset({'cashier_id': self.sales_b.id}, request=req)
        ids = set(qs.values_list('id', flat=True))
        self.assertEqual(ids, {self.sale_b.id})

    def test_sellers_endpoint_lists_everyone_who_sold(self):
        factory = APIRequestFactory()
        request = factory.get('/api/sales/sellers/')
        force_authenticate(request, user=self.manager)
        response = SaleViewSet.as_view({'get': 'sellers'})(request)
        self.assertEqual(response.status_code, 200)
        ids = {row['id'] for row in response.data}
        self.assertTrue({self.sales_a.id, self.sales_b.id}.issubset(ids))

    def test_sellers_endpoint_sales_agent_sees_only_self(self):
        factory = APIRequestFactory()
        request = factory.get('/api/sales/sellers/')
        force_authenticate(request, user=self.sales_a)
        response = SaleViewSet.as_view({'get': 'sellers'})(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data], [self.sales_a.id])

    def test_build_queryset_admin_sees_all(self):
        factory = RequestFactory()
        req = factory.get('/api/sales/')
        req.user = self.admin
        qs = SaleService().build_queryset({}, request=req)
        ids = set(qs.values_list('id', flat=True))
        self.assertIn(self.sale_a.id, ids)
        self.assertIn(self.sale_b.id, ids)

    def test_dashboard_summary_scoped_for_sales(self):
        factory = APIRequestFactory()
        request = factory.get('/api/sales/dashboard-summary/')
        force_authenticate(request, user=self.sales_a)
        view = SaleViewSet.as_view({'get': 'dashboard_summary'})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        # Only sales_a's sale contributes to today total.
        self.assertEqual(float(response.data['today']['total']), 100.0)
        self.assertEqual(response.data['today']['sales_count'], 1)

    def test_dashboard_summary_manager_sees_store_total(self):
        factory = APIRequestFactory()
        request = factory.get('/api/sales/dashboard-summary/')
        force_authenticate(request, user=self.manager)
        view = SaleViewSet.as_view({'get': 'dashboard_summary'})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(response.data['today']['total']), 300.0)

    def test_manager_pack_excludes_view_all(self):
        manager_role = Role.objects.get(name=ROLE_MANAGER)
        self.assertFalse(
            manager_role.permissions.filter(
                module='sales', action='view_all',
            ).exists()
        )
