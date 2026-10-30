"""Status filters for voided/cancelled sales; admin-only void and unvoid."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from products.models import Category, Product
from sales.models import Customer, CustomerWalletTransaction, Sale, SaleItem, SaleRefund
from sales.refunds import SaleRefundService
from sales.unvoid import uncancel_sale, unvoid_sale
from utils.tests.api_test_base import ManagerAPITestCase

User = get_user_model()


class SaleStatusFilterTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.customer = Customer.objects.create(name='Status Cust', phone='0700000001')
        cls.completed = Sale.objects.create(
            cashier=cls.manager_user,
            customer=cls.customer,
            status='completed',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('40'),
            payment_method='cash',
        )
        cls.voided = Sale.objects.create(
            cashier=cls.manager_user,
            customer=cls.customer,
            status='completed',
            refund_status='refunded',
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('50'),
            payment_method='cash',
        )
        cls.cancelled = Sale.objects.create(
            cashier=cls.manager_user,
            customer=cls.customer,
            status='cancelled',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            amount_paid=Decimal('0'),
            payment_method='cash',
        )

    def test_status_completed_excludes_fully_voided(self):
        res = self.client.get('/api/sales/', {'status': 'completed'})
        self.assertEqual(res.status_code, 200)
        ids = {row['id'] for row in res.data.get('results', res.data)}
        self.assertIn(self.completed.id, ids)
        self.assertNotIn(self.voided.id, ids)

    def test_status_voided_lists_refunded_only(self):
        res = self.client.get('/api/sales/', {'status': 'voided'})
        self.assertEqual(res.status_code, 200)
        ids = {row['id'] for row in res.data.get('results', res.data)}
        self.assertEqual(ids, {self.voided.id})

    def test_status_cancelled(self):
        res = self.client.get('/api/sales/', {'status': 'cancelled'})
        self.assertEqual(res.status_code, 200)
        ids = {row['id'] for row in res.data.get('results', res.data)}
        self.assertEqual(ids, {self.cancelled.id})

    def test_voided_date_uses_refund_day_not_sale_day(self):
        """Past sale voided today appears when filtering voided + today's dates."""
        cat = Category.objects.create(name='Void Date Cat', is_active=True)
        product = Product.objects.create(
            name='Void Date Product',
            sku='VOID-DATE-1',
            category=cat,
            price=Decimal('30'),
            stock_quantity=4,
            track_stock=True,
            is_active=True,
        )
        past = timezone.now() - timedelta(days=10)
        past_sale = Sale.objects.create(
            cashier=self.manager_user,
            customer=self.customer,
            status='completed',
            subtotal=Decimal('30'),
            total=Decimal('30'),
            amount_paid=Decimal('30'),
            payment_method='cash',
            occurred_at=past,
        )
        SaleItem.objects.create(
            sale=past_sale,
            product=product,
            quantity=1,
            unit_price=Decimal('30'),
            subtotal=Decimal('30'),
            unit_cost=Decimal('10'),
        )
        SaleRefundService().create_refund(
            past_sale,
            reason='voided today though sale is old',
            user=self.manager_user,
            full=True,
        )
        past_sale.refresh_from_db()
        self.assertEqual(past_sale.refund_status, 'refunded')

        today = timezone.localdate().isoformat()
        # Sale-day filter would miss this (occurred 10 days ago).
        by_sale_day = self.client.get(
            '/api/sales/',
            {'status': 'completed', 'date_from': today, 'date_to': today},
        )
        completed_ids = {row['id'] for row in by_sale_day.data.get('results', by_sale_day.data)}
        self.assertNotIn(past_sale.id, completed_ids)

        voided_today = self.client.get(
            '/api/sales/',
            {'status': 'voided', 'date_from': today, 'date_to': today},
        )
        self.assertEqual(voided_today.status_code, 200)
        voided_ids = {row['id'] for row in voided_today.data.get('results', voided_today.data)}
        self.assertIn(past_sale.id, voided_ids)


class AdminOnlyVoidTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.cat = Category.objects.create(name='Void Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Void Product',
            sku='VOID-1',
            category=cls.cat,
            price=Decimal('100'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='Void Cust', phone='0700000002')
        cls.sale = Sale.objects.create(
            cashier=cls.manager_user,
            customer=cls.customer,
            status='completed',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('100'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=1,
            unit_price=Decimal('100'),
            subtotal=Decimal('100'),
        )

    def test_manager_cannot_void_or_rollback(self):
        void = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'full': True, 'reason': 'mistake'},
            format='json',
        )
        self.assertEqual(void.status_code, status.HTTP_403_FORBIDDEN)

        rb = self.client.post(
            f'/api/sales/{self.sale.id}/rollback/',
            {'reason': 'duplicate'},
            format='json',
        )
        self.assertEqual(rb.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_void(self):
        admin = User.objects.create_user(username='void-admin', password='pass', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        res = client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'full': True, 'reason': 'customer return'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')


class UnvoidTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = Category.objects.create(name='Unvoid Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Unvoid Product',
            sku='UNVOID-1',
            category=cls.cat,
            price=Decimal('200'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Debt Cust',
            phone='0700000003',
            wallet_balance=Decimal('0'),
        )

    def setUp(self):
        super().setUp()
        self.sale = Sale.objects.create(
            cashier=self.manager_user,
            customer=self.customer,
            status='completed',
            subtotal=Decimal('200'),
            total=Decimal('200'),
            amount_paid=Decimal('50'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('200'),
            subtotal=Decimal('200'),
            unit_cost=Decimal('80'),
        )
        self.customer.wallet_balance = Decimal('-150')
        self.customer.save(update_fields=['wallet_balance'])
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('150'),
            balance_after=self.customer.wallet_balance,
            sale=self.sale,
            reference=self.sale.sale_number,
            notes='Sale debt',
            created_by=self.manager_user,
        )

    def test_unvoid_restores_debt_after_full_void(self):
        refund = SaleRefundService().create_refund(
            self.sale,
            reason='mistaken void',
            user=self.manager_user,
            full=True,
        )
        self.sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        balance_after_void = self.customer.wallet_balance

        restored = unvoid_sale(
            sale=self.sale,
            reason='restore customer debt',
            user=self.manager_user,
        )
        self.customer.refresh_from_db()
        self.assertEqual(restored.refund_status, 'none')
        self.assertFalse(SaleRefund.objects.filter(pk=refund.pk).exists())
        self.assertLess(self.customer.wallet_balance, balance_after_void)

    def test_manager_cannot_unvoid_without_permission(self):
        SaleRefundService().create_refund(
            self.sale,
            reason='mistaken void',
            user=self.manager_user,
            full=True,
        )
        res = self.client.post(
            f'/api/sales/{self.sale.id}/unvoid/',
            {'reason': 'fix debt'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')

    def test_manager_unvoid_when_permission_granted(self):
        from accounts.models import Permission
        from accounts.role_definitions import ROLE_MANAGER, ensure_permissions

        ensure_permissions()
        Role.objects.get(name=ROLE_MANAGER).permissions.add(
            Permission.objects.get(module='sales', action='unvoid')
        )
        SaleRefundService().create_refund(
            self.sale,
            reason='mistaken void',
            user=self.manager_user,
            full=True,
        )
        res = self.client.post(
            f'/api/sales/{self.sale.id}/unvoid/',
            {'reason': 'fix debt'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'none')

    def test_admin_unvoid_endpoint(self):
        SaleRefundService().create_refund(
            self.sale,
            reason='mistaken void',
            user=self.manager_user,
            full=True,
        )
        admin = User.objects.create_user(username='unvoid-admin', password='pass', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        res = client.post(
            f'/api/sales/{self.sale.id}/unvoid/',
            {'reason': 'fix debt'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'none')

    def test_uncancel_restores_holding(self):
        cancelled = Sale.objects.create(
            cashier=self.manager_user,
            customer=self.customer,
            status='cancelled',
            subtotal=Decimal('20'),
            total=Decimal('20'),
            amount_paid=Decimal('0'),
            payment_method='cash',
        )
        out = uncancel_sale(sale=cancelled, reason='still needed', user=self.manager_user)
        self.assertEqual(out.status, 'holding')

    def test_manager_cannot_uncancel_via_endpoint(self):
        cancelled = Sale.objects.create(
            cashier=self.manager_user,
            customer=self.customer,
            status='cancelled',
            subtotal=Decimal('20'),
            total=Decimal('20'),
            amount_paid=Decimal('0'),
            payment_method='cash',
        )
        res = self.client.post(
            f'/api/sales/{cancelled.id}/unvoid/',
            {'reason': 'reopen'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        cancelled.refresh_from_db()
        self.assertEqual(cancelled.status, 'cancelled')
