"""Cashier sales wait for manager approval before stock, books, or receipts."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN
from agents.push import FakePushNotifier, set_push_notifier
from approvals.apply import apply_pending_change
from approvals.models import PendingChange
from approvals.permissions import user_can_check
from approvals.registry import ACTION_SALE_COMPLETE, CHECKER_MODULE_BY_ACTION
from daily_notes.models import DailyNote, DailyTask
from inventory.models import StockMovement
from products.models import Category, Product
from sales.models import Sale
from sales.sale_completion_approval import (
    QUEUE_REASON,
    WAITING_MESSAGE,
    cancel_queued_sale,
    complete_queued_sale,
    payment_payload_from_inputs,
    pending_sale_complete_change,
    queue_sale_complete,
    sale_completion_should_wait,
    user_can_complete_sales,
)
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class SaleCompletionHelperTests(TestCase):
    def test_user_without_profile_completes_immediately(self):
        user = User.objects.create_user('bare_till', password='x')
        self.assertTrue(user_can_complete_sales(user))
        self.assertFalse(sale_completion_should_wait(user))

    def test_superuser_completes_immediately(self):
        user = User.objects.create_superuser('sa', email='sa@t.com', password='x')
        self.assertTrue(user_can_complete_sales(user))

    def test_legacy_manager_completes_immediately(self):
        user = User.objects.create_user('legacy_mgr', password='x')
        UserProfile.objects.create(user=user, role='manager')
        self.assertTrue(user_can_complete_sales(user))

    def test_legacy_cashier_must_wait(self):
        user = User.objects.create_user('legacy_cash', password='x')
        UserProfile.objects.create(user=user, role='cashier')
        self.assertFalse(user_can_complete_sales(user))
        self.assertTrue(sale_completion_should_wait(user))

    def test_payment_payload_serializes_decimals(self):
        payload = payment_payload_from_inputs(
            payment_method='mpesa',
            amount_paid=Decimal('50.00'),
            allow_partial=True,
            wallet_amount=Decimal('10'),
            payment_reference='QHX1',
        )
        self.assertEqual(payload['amount_paid'], '50.00')
        self.assertEqual(payload['wallet_amount'], '10')
        self.assertTrue(payload['allow_partial'])
        self.assertEqual(payload['payment_reference'], 'QHX1')

    def test_checker_module_is_sales(self):
        self.assertEqual(CHECKER_MODULE_BY_ACTION[ACTION_SALE_COMPLETE], 'sales')

    def test_cancel_queued_sale_ignores_completed(self):
        sale = Sale.objects.create(
            sale_number='S-DONE',
            status='completed',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
        )
        self.assertEqual(cancel_queued_sale(sale).status, 'completed')

    def test_none_user_completes_immediately(self):
        self.assertTrue(user_can_complete_sales(None))

    def test_complete_empty_sale_rejected(self):
        user = User.objects.create_user('empty_till', password='x')
        sale = Sale.objects.create(
            sale_number='S-EMPTY',
            status='pending_approval',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
        )
        with self.assertRaises(ValidationError):
            complete_queued_sale(sale, user)

    def test_apply_sale_complete_requires_checker(self):
        sale = Sale.objects.create(
            sale_number='S-NO-CHECK',
            status='pending_approval',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
        )
        change = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            reason=QUEUE_REASON,
            status=PendingChange.STATUS_PENDING,
        )
        with self.assertRaises(ValidationError):
            apply_pending_change(change)
        sale = Sale.objects.create(
            sale_number='S-HOLD',
            status='holding',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('0'),
        )
        with self.assertRaises(ValidationError):
            complete_queued_sale(sale, User.objects.create_user('x', password='x'))


class SaleCompletionApprovalAPITests(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.manager_user = User.objects.create_user('sale_appr_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager_user,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        cls.admin = User.objects.create_superuser(
            'sale_appr_admin', email='saa@test.com', password='x'
        )
        UserProfile.objects.create(
            user=cls.admin,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.category = Category.objects.create(name='Till Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Till Item',
            sku='TILL-1',
            category=cls.category,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        self.notifier = FakePushNotifier()
        set_push_notifier(self.notifier)
        self.tenant, self.branch, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.sales_user
        )
        self.set_session_branch(self.tenant, self.branch)
        self.product.refresh_from_db()

    def tearDown(self):
        set_push_notifier(FakePushNotifier())
        super().tearDown()

    def set_session_branch(self, tenant, branch):
        session = self.client.session
        session['current_tenant_id'] = tenant.id
        session['current_branch_id'] = branch.id
        session.save()

    def _manager_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.manager_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        session = client.session
        session['current_tenant_id'] = self.tenant.id
        session['current_branch_id'] = self.branch.id
        session.save()
        return client

    def _sale_payload(self, quantity=1, amount=None):
        qty = Decimal(str(quantity))
        total = qty * Decimal('100.00')
        return {
            'items': [{'product_id': self.product.id, 'quantity': str(qty)}],
            'payment_method': 'cash',
            'amount_paid': str(amount if amount is not None else total),
            'sale_type': 'pos',
            'client_channel': 'web',
        }

    def test_salesperson_create_is_pending_stock_unchanged(self):
        response = self.client.post('/api/sales/', self._sale_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending_approval')
        self.assertEqual(response.data['message'], WAITING_MESSAGE)
        self.assertIn('pending_change', response.data)
        sale = Sale.objects.get(pk=response.data['id'])
        self.assertEqual(sale.status, 'pending_approval')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertFalse(StockMovement.objects.filter(reference=sale.sale_number).exists())
        self.assertTrue(
            PendingChange.objects.filter(
                action_type=ACTION_SALE_COMPLETE,
                entity_id=str(sale.id),
                status=PendingChange.STATUS_PENDING,
            ).exists()
        )

    def test_manager_create_completes_and_moves_stock(self):
        client = self._manager_client()
        response = client.post('/api/sales/', self._sale_payload(quantity=2), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'completed')
        self.assertNotIn('pending_change', response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 18)
        sale = Sale.objects.get(pk=response.data['id'])
        self.assertTrue(StockMovement.objects.filter(reference=sale.sale_number).exists())

    def test_salesperson_cannot_post_complete(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        response = self.client.post(f'/api/sales/{sale_id}/complete/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        sale = Sale.objects.get(pk=sale_id)
        self.assertEqual(sale.status, 'pending_approval')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

    def test_manager_approve_completes_stock_and_notifies_cashier(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        sale_number = created.data['sale_number']
        client = self._manager_client()
        response = client.post(f'/api/sales/{sale_id}/complete/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 19)
        sale = Sale.objects.get(pk=sale_id)
        self.assertTrue(StockMovement.objects.filter(reference=sale.sale_number).exists())
        change = PendingChange.objects.get(
            action_type=ACTION_SALE_COMPLETE, entity_id=str(sale_id)
        )
        self.assertEqual(change.status, PendingChange.STATUS_APPROVED)
        self.assertTrue(
            DailyNote.objects.filter(
                author=self.sales_user, title__icontains=sale_number
            ).exists()
        )
        self.assertTrue(
            DailyTask.objects.filter(
                assigned_to=self.sales_user, title__icontains=sale_number
            ).exists()
        )
        self.assertTrue(
            any(
                item['user_id'] == self.sales_user.id
                and 'issue the receipt' in item['body']
                for item in self.notifier.sent
            )
        )

    def test_manager_reject_cancels_without_stock_move(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        client = self._manager_client()
        response = client.post(
            f'/api/sales/{sale_id}/reject-complete/',
            {'rejection_reason': 'Wrong prices'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sale = Sale.objects.get(pk=sale_id)
        self.assertEqual(sale.status, 'cancelled')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertFalse(StockMovement.objects.filter(reference=sale.sale_number).exists())
        change = PendingChange.objects.get(
            action_type=ACTION_SALE_COMPLETE, entity_id=str(sale_id)
        )
        self.assertEqual(change.status, PendingChange.STATUS_REJECTED)

    def test_receipt_is_blocked_while_pending(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        response = self.client.get(f'/api/sales/{sale_id}/receipt/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('manager will approve', response.data['error'].lower())

    def test_pending_sales_are_hidden_from_default_list_and_reports(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        listed = self.client.get('/api/sales/')
        ids = [row['id'] for row in listed.data.get('results', listed.data)]
        self.assertNotIn(sale_id, ids)

        awaiting = self.client.get('/api/sales/?status=pending_approval')
        awaiting_ids = [row['id'] for row in awaiting.data.get('results', awaiting.data)]
        self.assertIn(sale_id, awaiting_ids)

        from reports.views import sale_report_queryset

        self.assertFalse(sale_report_queryset().filter(pk=sale_id).exists())

    def test_manager_pending_list_includes_cashier_sales(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        client = self._manager_client()
        listed = client.get('/api/sales/?status=pending_approval')
        ids = [row['id'] for row in listed.data.get('results', listed.data)]
        self.assertIn(sale_id, ids)

    def test_staff_without_sales_approve_cannot_check_sale_complete(self):
        staff = User.objects.create_user('staff_no_approve', password='x', is_staff=True)
        UserProfile.objects.create(user=staff, role='cashier', is_active=True)
        self.assertFalse(user_can_check(staff, ACTION_SALE_COMPLETE))
        self.assertTrue(user_can_check(self.manager_user, ACTION_SALE_COMPLETE))

    def test_queue_is_idempotent_and_apply_handler_completes(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale = Sale.objects.get(pk=created.data['id'])
        factory = RequestFactory()
        request = factory.post('/api/sales/')
        request.user = self.sales_user
        first = queue_sale_complete(
            request, sale, payment_payload=payment_payload_from_inputs(
                payment_method='cash', amount_paid=sale.amount_paid
            )
        )
        second = queue_sale_complete(
            request, sale, payment_payload=payment_payload_from_inputs(
                payment_method='cash', amount_paid=sale.amount_paid
            )
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(QUEUE_REASON, first.reason)
        self.assertEqual(pending_sale_complete_change(sale).id, first.id)

        first.checked_by = self.manager_user
        apply_pending_change(first)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 19)

    def test_complete_uses_existing_payment_reference_and_handles_push_errors(self):
        from unittest.mock import patch

        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale = Sale.objects.get(pk=created.data['id'])
        sale.payment_reference = 'KEEP-ME'
        sale.save(update_fields=['payment_reference'])
        with patch(
            'accounting.services.create_sale_journal_entry',
            side_effect=RuntimeError('books down'),
        ), patch(
            'agents.push.get_push_notifier',
            side_effect=RuntimeError('push down'),
        ):
            complete_queued_sale(sale, self.manager_user, {'amount_paid': '100.00'})
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        self.assertEqual(sale.payment_reference, 'KEEP-ME')

        with patch(
            'agents.push.get_push_notifier',
            side_effect=RuntimeError('push down'),
        ):
            from sales.sale_completion_approval import notify_cashier_sale_rejected

            notify_cashier_sale_rejected(sale, self.manager_user, 'nope')

    def test_salesperson_holding_checkout_is_pending(self):
        from sales.services import SaleService

        holding = SaleService().save_holding_sale(
            self.sales_user,
            [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '100.00'}],
            branch=self.branch,
        )
        response = self.client.post(
            f'/api/sales/{holding.id}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['status'], 'pending_approval')
        self.assertEqual(response.data['message'], WAITING_MESSAGE)
        holding.refresh_from_db()
        self.assertEqual(holding.status, 'pending_approval')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
