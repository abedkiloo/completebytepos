"""Sales visibility: own sales by default; admin / sales.view_all see store-wide."""

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
from sales.visibility import user_sees_all_sales
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
        self.assertFalse(user_sees_all_sales(self.manager))
        self.assertFalse(user_sees_all_sales(self.sales_a))

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

    def test_build_queryset_manager_sees_own_only(self):
        # Manager with no personal sales → empty / no other cashiers.
        factory = RequestFactory()
        req = factory.get('/api/sales/')
        req.user = self.manager
        qs = SaleService().build_queryset({}, request=req)
        ids = set(qs.values_list('id', flat=True))
        self.assertNotIn(self.sale_a.id, ids)
        self.assertNotIn(self.sale_b.id, ids)

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

    def test_dashboard_summary_manager_does_not_see_others(self):
        factory = APIRequestFactory()
        request = factory.get('/api/sales/dashboard-summary/')
        force_authenticate(request, user=self.manager)
        view = SaleViewSet.as_view({'get': 'dashboard_summary'})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(response.data['today']['total']), 0.0)

    def test_manager_pack_excludes_view_all(self):
        manager_role = Role.objects.get(name=ROLE_MANAGER)
        self.assertFalse(
            manager_role.permissions.filter(
                module='sales', action='view_all',
            ).exists()
        )
