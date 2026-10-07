"""Sale accountability timeline — who recorded, approved, voided, cancelled."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status

from accounts.models import AuditLog, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE, ACTION_SALE_REFUND
from products.models import Category, Product
from sales.activity import build_sale_activity
from sales.models import Sale, SaleItem, SaleRefund
from utils.tests.api_test_base import ManagerAPITestCase


class SaleActivityTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.cashier = User.objects.create_user('act_cashier', password='x')
        UserProfile.objects.create(
            user=cls.cashier,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.cat = Category.objects.create(name='ActCat', is_active=True)
        cls.product = Product.objects.create(
            name='Act Item',
            sku='ACT-1',
            category=cls.cat,
            price=Decimal('50'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-ACT-1',
            status='completed',
            subtotal=Decimal('50'),
            total=Decimal('50'),
            payment_method='cash',
            amount_paid=Decimal('50'),
            cashier=cls.cashier,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=1,
            unit_price=Decimal('50'),
            subtotal=Decimal('50'),
        )

    def test_build_sale_activity_includes_recorded_approve_and_void(self):
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(self.sale.pk),
            entity_repr=self.sale.sale_number,
            original_values={},
            proposed_values={},
            reason='Checkout complete',
            status=PendingChange.STATUS_APPROVED,
            made_by=self.cashier,
            checked_by=self.manager_user,
            checked_at=timezone.now(),
        )
        SaleRefund.objects.create(
            sale=self.sale,
            refund_number='RF-ACT-1',
            refund_type='full',
            amount=Decimal('50'),
            reason='Customer return',
            refunded_by=self.manager_user,
        )
        self.sale.refund_status = 'refunded'
        self.sale.save(update_fields=['refund_status'])

        events = build_sale_activity(self.sale)
        kinds = [e['kind'] for e in events]
        self.assertIn('recorded', kinds)
        self.assertIn('submitted', kinds)
        self.assertIn('approved', kinds)
        self.assertIn('void', kinds)

        recorded = next(e for e in events if e['kind'] == 'recorded')
        self.assertEqual(recorded['actor'], 'act_cashier')
        self.assertEqual(recorded['actor_role'], 'Cashier')

        approved = next(e for e in events if e['kind'] == 'approved')
        self.assertEqual(approved['label'], 'Sale approved')
        self.assertEqual(approved['actor'], self.manager_user.username)

        voided = next(e for e in events if e['kind'] == 'void')
        self.assertEqual(voided['label'], 'Void / refund applied')
        self.assertIn('Customer return', voided['comment'])

    def test_cancelled_sale_uses_audit_actor(self):
        self.sale.status = 'cancelled'
        self.sale.save(update_fields=['status'])
        AuditLog.objects.create(
            module='sales',
            action='holding_cancel',
            object_type='sales.Sale',
            object_id=str(self.sale.pk),
            user=self.manager_user,
            username_snapshot=self.manager_user.username,
            changes={'sale_number': self.sale.sale_number},
        )
        events = build_sale_activity(self.sale)
        cancelled = next(e for e in events if e['kind'] == 'cancelled')
        self.assertEqual(cancelled['actor'], self.manager_user.username)
        self.assertEqual(cancelled['label'], 'Sale cancelled')

    def test_sale_detail_api_includes_activity(self):
        PendingChange.objects.create(
            action_type=ACTION_SALE_REFUND,
            entity_type='sales.Sale',
            entity_id=str(self.sale.pk),
            entity_repr=self.sale.sale_number,
            original_values={},
            proposed_values={},
            reason='Wrong item',
            status=PendingChange.STATUS_APPROVED,
            made_by=self.cashier,
            checked_by=self.manager_user,
            checked_at=timezone.now(),
        )
        resp = self.client.get(f'/api/sales/{self.sale.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIsInstance(resp.data.get('activity'), list)
        labels = [e['label'] for e in resp.data['activity']]
        self.assertTrue(any('Sale recorded' == label for label in labels))
        self.assertTrue(any('Void / refund' in label for label in labels))

    def test_sale_list_omits_activity(self):
        resp = self.client.get('/api/sales/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results') or resp.data
        if results:
            self.assertIsNone(results[0].get('activity'))

    def test_sale_list_uses_slim_items_without_nested_product(self):
        resp = self.client.get('/api/sales/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results') or resp.data
        self.assertTrue(results)
        row = results[0]
        self.assertIn('items', row)
        self.assertIsNone(row.get('approval_details'))
        self.assertIsNone(row.get('activity'))
        if row['items']:
            line = row['items'][0]
            self.assertIn('product_name', line)
            self.assertIn('quantity', line)
            self.assertNotIn('product', line)
            self.assertNotIn('variants', line)

        detail = self.client.get(f'/api/sales/{self.sale.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        detail_items = detail.data.get('items') or []
        self.assertTrue(detail_items)
        self.assertIn('product', detail_items[0])
