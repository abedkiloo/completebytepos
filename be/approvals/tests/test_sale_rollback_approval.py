"""Sale rollback queues for admin approval before stock and books change."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN, ensure_permissions
from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_ROLLBACK
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase


class SaleRollbackApprovalAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        disable_maker_checker()
        ensure_permissions()
        perm = Permission.objects.get(module='sales', action='rollback')
        Role.objects.get(name=ROLE_MANAGER).permissions.add(perm)
        cls.cat = Category.objects.create(name='RbApprCat', is_active=True)
        cls.product = Product.objects.create(
            name='Rb Appr Item',
            sku='RB-APPR-1',
            category=cls.cat,
            price=Decimal('20'),
            stock_quantity=6,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-RB-APPR',
            status='completed',
            subtotal=Decimal('40'),
            total=Decimal('40'),
            payment_method='cash',
            amount_paid=Decimal('40'),
            cashier=cls.manager_user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('20'),
            subtotal=Decimal('40'),
        )

    def test_cannot_queue_rollback_after_refund(self):
        self.sale.refund_status = 'refunded'
        self.sale.save(update_fields=['refund_status'])
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'Already refunded'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rollback_requires_reason_when_queuing(self):
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': '  '},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_with_permission_queues_rollback(self):
        stock_before = self.product.stock_quantity
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'Wrong till'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        change = PendingChange.objects.get(action_type=ACTION_SALE_ROLLBACK)
        self.assertEqual(change.status, PendingChange.STATUS_PENDING)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'none')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, stock_before)
        self.assertFalse(SaleRefund.objects.filter(sale=self.sale).exists())
        detail = self.client.get(f'/api/sales/{self.sale.id}/')
        self.assertFalse(detail.data['can_rollback'])

    def test_duplicate_pending_rollback_blocked(self):
        first = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'First'},
            format='json',
        )
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        second = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'Second'},
            format='json',
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_cannot_self_approve_rollback(self):
        self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'Mistake'},
            format='json',
        )
        change = PendingChange.objects.get(action_type=ACTION_SALE_ROLLBACK)
        deny = self.client.post(f'/api/approvals/pending-changes/{change.id}/approve/')
        self.assertIn(deny.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))

    def test_admin_approval_applies_rollback(self):
        stock_before = self.product.stock_quantity
        queued = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'Duplicate checkout'},
            format='json',
        )
        self.assertEqual(queued.status_code, status.HTTP_202_ACCEPTED, queued.data)
        change = PendingChange.objects.get(action_type=ACTION_SALE_ROLLBACK)

        checker = User.objects.create_superuser(
            'rb_checker', email='rb@test.com', password='x'
        )
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        checker_client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        checker_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

        approved = checker_client.post(f'/api/approvals/pending-changes/{change.id}/approve/')
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)

        self.sale.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        self.assertEqual(self.product.stock_quantity, stock_before + 2)
        refund = SaleRefund.objects.get(sale=self.sale)
        self.assertEqual(refund.refund_type, 'rollback')
