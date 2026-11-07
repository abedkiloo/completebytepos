"""Permanently remove returned sales from history without touching reports."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from products.models import Category, Product
from reports.sale_scope import posted_sales
from sales.models import Sale, SaleItem
from sales.sale_completion_approval import (
    discard_returned_sale,
    sale_can_be_permanently_discarded,
)
from sales.services import SaleService
from utils.tests.api_test_base import ManagerAPITestCase


def _mark_returned_from_completed(sale, *, reason='Wrong items'):
    PendingChange.objects.create(
        action_type=ACTION_SALE_COMPLETE,
        entity_type='sales.Sale',
        entity_id=str(sale.pk),
        entity_repr=sale.sale_number,
        reason=reason,
        status=PendingChange.STATUS_REJECTED,
        rejection_reason=reason,
        original_values={
            'status': 'completed',
            'returned_from_status': 'completed',
        },
    )


class DiscardReturnedSaleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('discard_admin', password='x', is_staff=True)
        self.category = Category.objects.create(name='Discard Cat', is_active=True)
        self.product = Product.objects.create(
            name='Discard Item',
            sku='DISC-1',
            category=self.category,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='SALE-DISCARD-1',
            status='holding',
            sale_type='pos',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            cashier=self.user,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            unit_cost=Decimal('40'),
            subtotal=Decimal('100'),
        )
        _mark_returned_from_completed(self.sale)

    def test_eligible_returned_sale_can_discard(self):
        self.assertTrue(sale_can_be_permanently_discarded(self.sale))

    def test_completed_sale_cannot_discard(self):
        self.sale.status = 'completed'
        self.sale.save(update_fields=['status'])
        self.assertFalse(sale_can_be_permanently_discarded(self.sale))

    def test_discard_requires_confirm_and_sale_number(self):
        with self.assertRaises(ValidationError):
            discard_returned_sale(
                self.sale,
                user=self.user,
                reason='Mistake',
                confirm=False,
                confirm_sale_number=self.sale.sale_number,
            )
        with self.assertRaises(ValidationError):
            discard_returned_sale(
                self.sale,
                user=self.user,
                reason='Mistake',
                confirm=True,
                confirm_sale_number='WRONG',
            )

    def test_discard_hides_from_list_and_posted_sales(self):
        discarded = discard_returned_sale(
            self.sale,
            user=self.user,
            reason='Customer cancelled — do not rekey',
            confirm=True,
            confirm_sale_number=self.sale.sale_number,
        )
        self.assertEqual(discarded.status, 'discarded')
        self.assertFalse(posted_sales().filter(pk=self.sale.pk).exists())

        listed = SaleService().build_queryset({}, request=None)
        self.assertFalse(listed.filter(pk=self.sale.pk).exists())


class DiscardReturnedSaleAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ensure_permissions()
        sync_default_roles()

    def _admin_client(self):
        admin = User.objects.create_user('discard_api_admin', password='x', is_staff=True)
        UserProfile.objects.create(
            user=admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_discard_returned_endpoint(self):
        sale = Sale.objects.create(
            sale_number='SALE-DISCARD-API',
            status='holding',
            sale_type='pos',
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            cashier=self.manager_user,
            occurred_at=timezone.now(),
        )
        _mark_returned_from_completed(sale, reason='Fix qty')
        admin = self._admin_client()
        res = admin.post(
            f'/api/sales/{sale.id}/discard-returned/',
            {
                'confirm': True,
                'confirm_sale_number': sale.sale_number,
                'reason': 'Will not be rekeyed',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'discarded')
