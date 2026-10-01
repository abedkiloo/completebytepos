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
from accounting.models import Transaction
from accounting.services import create_sale_journal_entry
from reports.views import sale_report_queryset
from sales.models import Sale
from sales.sale_completion_approval import (
    QUEUE_REASON,
    UNEDITED_RETURN_MESSAGE,
    WAITING_MESSAGE,
    cancel_queued_sale,
    complete_queued_sale,
    notify_cashier_sale_approved,
    notify_cashier_sale_rejected,
    payment_payload_from_inputs,
    pending_sale_complete_change,
    queue_sale_complete,
    restore_queued_sale_for_approval,
    return_queued_sale_for_correction,
    sale_completion_should_wait,
    sale_needs_salesperson_action,
    sale_rejection_reason,
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
        pending = Sale.objects.create(
            sale_number='S-CAN',
            status='pending_approval',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
        )
        self.assertEqual(cancel_queued_sale(pending).status, 'cancelled')

    def test_return_queued_sale_puts_pending_back_on_holding(self):
        sale = Sale.objects.create(
            sale_number='S-RET',
            status='pending_approval',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
        )
        self.assertEqual(return_queued_sale_for_correction(sale).status, 'holding')
        sale.status = 'completed'
        sale.save(update_fields=['status'])
        self.assertEqual(return_queued_sale_for_correction(sale).status, 'completed')
        self.assertEqual(restore_queued_sale_for_approval(sale).status, 'completed')
        sale.status = 'holding'
        sale.save(update_fields=['status'])
        restored = restore_queued_sale_for_approval(sale)
        self.assertEqual(restored.status, 'pending_approval')
        change = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            reason=QUEUE_REASON,
            status=PendingChange.STATUS_PENDING,
            apply_payload={'allow_partial': True, 'use_wallet': True, 'wallet_amount': '2'},
        )
        sale.status = 'holding'
        sale.payment_method = 'mpesa'
        sale.amount_paid = Decimal('5.00')
        sale.payment_reference = 'R1'
        sale.save(update_fields=['status', 'payment_method', 'amount_paid', 'payment_reference'])
        restored = restore_queued_sale_for_approval(sale, change)
        self.assertEqual(restored.status, 'pending_approval')
        change.refresh_from_db()
        self.assertEqual(change.apply_payload['payment_method'], 'mpesa')
        self.assertEqual(change.apply_payload['amount_paid'], '5.00')
        self.assertTrue(change.apply_payload['allow_partial'])
        self.assertEqual(change.apply_payload['payment_reference'], 'R1')

    def test_cashier_push_errors_are_swallowed(self):
        from unittest.mock import patch

        cashier = User.objects.create_user('push_till', password='x')
        sale = Sale.objects.create(
            sale_number='S-PUSH',
            status='holding',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
            cashier=cashier,
        )
        with patch('agents.push.get_push_notifier', side_effect=RuntimeError('push')):
            notify_cashier_sale_approved(sale, cashier)
            notify_cashier_sale_rejected(sale, cashier, 'Wrong till')

    def test_none_user_completes_immediately(self):
        self.assertTrue(user_can_complete_sales(None))

    def test_complete_empty_sale_rejected(self):
        user = User.objects.create_user('empty_till', password='x')
        sale = Sale.objects.create(
            sale_number='S-EMPTY',
            status='awaiting_payment',
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
            status='awaiting_payment',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('0'),
        )
        with self.assertRaises(ValidationError):
            complete_queued_sale(sale, User.objects.create_user('x', password='x'))

    def test_rejected_holding_needs_salesperson_action(self):
        holding = Sale.objects.create(
            sale_number='S-HOLD-CART',
            status='holding',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('0'),
        )
        self.assertFalse(sale_needs_salesperson_action(holding))
        self.assertEqual(sale_rejection_reason(holding), '')

        returned = Sale.objects.create(
            sale_number='S-HOLD-RETURN',
            status='holding',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('0'),
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(returned.pk),
            entity_repr=returned.sale_number,
            reason=QUEUE_REASON,
            status=PendingChange.STATUS_REJECTED,
            rejection_reason='Wrong prices',
        )
        self.assertTrue(sale_needs_salesperson_action(returned))
        self.assertEqual(sale_rejection_reason(returned), 'Wrong prices')


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

    def _admin_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.admin)
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
        self.assertEqual(sale.amount_paid, Decimal('100.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertFalse(StockMovement.objects.filter(reference=sale.sale_number).exists())
        self.assertFalse(
            Transaction.objects.filter(reference_type='sale', reference_id=sale.id).exists()
        )
        self.assertIsNone(create_sale_journal_entry(sale))
        self.assertFalse(
            Transaction.objects.filter(reference_type='sale', reference_id=sale.id).exists()
        )
        self.assertFalse(sale_report_queryset().filter(pk=sale.pk).exists())
        self.assertTrue(
            PendingChange.objects.filter(
                action_type=ACTION_SALE_COMPLETE,
                entity_id=str(sale.id),
                status=PendingChange.STATUS_PENDING,
            ).exists()
        )
        manager_note = DailyNote.objects.get(
            assigned_to=self.manager_user,
            content__contains=f'ref: sale_complete/{sale.id}',
        )
        self.assertEqual(manager_note.board_column, 'todo')
        self.assertIn('Clear and move', manager_note.title)
        self.assertFalse(manager_note.is_done)

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
        self.assertFalse(
            DailyNote.objects.filter(
                title__startswith='Clear and move:',
                content__contains=f'ref: sale_complete/{sale.id}',
            ).exists()
        )

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
        from datetime import date

        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        sale_number = created.data['sale_number']
        leftover = DailyTask.objects.create(
            task_date=date.today(),
            title=f'Sale #{sale_number} was approved',
            description='Collect payment to complete it.',
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        client = self._manager_client()
        response = client.post(f'/api/sales/{sale_id}/complete/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 19)
        sale = Sale.objects.get(pk=sale_id)
        self.assertEqual(sale.status, 'completed')
        self.assertEqual(sale.amount_paid, Decimal('100.00'))
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
            any(
                item['user_id'] == self.sales_user.id
                and 'print the receipt' in item['body'].lower()
                for item in self.notifier.sent
            )
        )
        manager_note = DailyNote.objects.get(
            assigned_to=self.manager_user,
            content__contains=f'ref: sale_complete/{sale_id}',
        )
        self.assertEqual(manager_note.board_column, 'past')
        self.assertTrue(manager_note.is_done)
        leftover.refresh_from_db()
        self.assertTrue(leftover.is_done)
        self.assertFalse(
            DailyTask.objects.filter(
                assigned_to=self.sales_user,
                is_done=False,
                title__icontains=sale_number,
            ).exists()
        )

    def test_partial_debt_is_recorded_on_send_and_posted_on_approve(self):
        from sales.models import Customer

        customer = Customer.objects.create(name='Jane Debt', phone='0700000001')
        payload = self._sale_payload(amount='40.00')
        payload['customer_id'] = customer.id
        payload['allow_partial_payment'] = True
        created = self.client.post('/api/sales/', payload, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        sale = Sale.objects.get(pk=created.data['id'])
        self.assertEqual(sale.status, 'pending_approval')
        self.assertEqual(sale.amount_paid, Decimal('40.00'))
        customer.refresh_from_db()
        self.assertEqual(customer.wallet_balance, Decimal('0'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

        client = self._manager_client()
        approved = client.post(f'/api/sales/{sale.id}/complete/', {}, format='json')
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)
        self.assertEqual(approved.data['status'], 'completed')
        sale.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal('40.00'))
        customer.refresh_from_db()
        self.assertEqual(customer.wallet_balance, Decimal('-60.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 19)

    def test_cannot_collect_before_manager_approves(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        response = self.client.post(
            f'/api/sales/{sale_id}/collect/',
            {'payment_method': 'cash', 'amount_paid': '100.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_reject_returns_sale_with_sticky_note(self):
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
        self.assertEqual(sale.status, 'holding')
        self.assertEqual(sale.amount_paid, Decimal('100.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertFalse(StockMovement.objects.filter(reference=sale.sale_number).exists())
        self.assertFalse(
            Transaction.objects.filter(reference_type='sale', reference_id=sale.id).exists()
        )
        self.assertFalse(sale_report_queryset().filter(pk=sale.pk).exists())
        change = PendingChange.objects.get(
            action_type=ACTION_SALE_COMPLETE, entity_id=str(sale_id)
        )
        self.assertEqual(change.status, PendingChange.STATUS_REJECTED)
        manager_note = DailyNote.objects.get(
            assigned_to=self.manager_user,
            content__contains=f'ref: sale_complete/{sale_id}',
        )
        self.assertEqual(manager_note.board_column, 'past')
        self.assertTrue(manager_note.is_done)
        sticky = DailyNote.objects.get(
            assigned_to=self.sales_user,
            is_sticky=True,
            content__contains='Wrong prices',
        )
        self.assertIn(sale.sale_number, sticky.content)
        self.assertIn(f'sale_id: {sale_id}', sticky.content)
        self.assertIn(f'id: {change.id}', sticky.content)

        opened = self.client.get(f'/api/sales/{sale_id}/')
        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        self.assertEqual(opened.data['status'], 'holding')
        self.assertTrue(opened.data['needs_salesperson_action'])
        self.assertEqual(len(opened.data['items']), 1)
        self.assertEqual(opened.data['items'][0]['product_id'], self.product.id)
        self.assertEqual(opened.data['items'][0]['quantity'], 1)

        ordinary_hold = Sale.objects.create(
            sale_number='S-CART-HOLD',
            status='holding',
            cashier=self.sales_user,
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('0'),
        )
        awaiting = self.client.get('/api/sales/?status=pending_approval')
        awaiting_rows = awaiting.data.get('results', awaiting.data)
        awaiting_by_id = {row['id']: row for row in awaiting_rows}
        self.assertIn(sale_id, awaiting_by_id)
        self.assertNotIn(ordinary_hold.id, awaiting_by_id)
        returned = awaiting_by_id[sale_id]
        self.assertTrue(returned['needs_salesperson_action'])
        self.assertEqual(returned['rejection_reason'], 'Wrong prices')
        self.assertEqual(returned['status'], 'holding')

        manager_awaiting = self._manager_client().get('/api/sales/?status=pending_approval')
        manager_ids = [row['id'] for row in manager_awaiting.data.get('results', manager_awaiting.data)]
        self.assertIn(sale_id, manager_ids)
        self.assertNotIn(ordinary_hold.id, manager_ids)

        unchanged = self.client.post(
            f'/api/approvals/pending-changes/{change.id}/resubmit/',
            {},
            format='json',
        )
        self.assertEqual(unchanged.status_code, status.HTTP_400_BAD_REQUEST)

        edited = self.client.post(
            '/api/sales/holding/',
            {
                'holding_id': sale_id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': '2',
                        'unit_price': '100.00',
                    }
                ],
                'client_channel': 'web',
            },
            format='json',
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK, edited.data)

        resubmit = self.client.post(
            f'/api/approvals/pending-changes/{change.id}/resubmit/',
            {},
            format='json',
        )
        self.assertEqual(resubmit.status_code, status.HTTP_200_OK, resubmit.data)
        sale.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual(sale.status, 'pending_approval')
        self.assertEqual(change.status, PendingChange.STATUS_PENDING)
        sticky.refresh_from_db()
        self.assertTrue(sticky.is_done)

    def test_salesperson_can_checkout_returned_sale_again(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        reject = self._manager_client().post(
            f'/api/sales/{sale_id}/reject-complete/',
            {'rejection_reason': 'Wrong prices'},
            format='json',
        )
        self.assertEqual(reject.status_code, status.HTTP_200_OK)
        blocked = self.client.post(
            f'/api/sales/{sale_id}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            'Update this sale',
            str(blocked.data.get('error') or blocked.data),
        )

        edited = self.client.post(
            '/api/sales/holding/',
            {
                'holding_id': sale_id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': '2',
                        'unit_price': '100.00',
                    }
                ],
                'client_channel': 'web',
            },
            format='json',
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK, edited.data)
        response = self.client.post(
            f'/api/sales/{sale_id}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': '200.00',
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        sale = Sale.objects.get(pk=sale_id)
        self.assertEqual(sale.status, 'pending_approval')
        self.assertEqual(sale.amount_paid, Decimal('200.00'))
        self.assertEqual(sale.items.get().quantity, Decimal('2'))
        sticky = DailyNote.objects.get(
            assigned_to=self.sales_user,
            is_sticky=True,
            content__contains=f'ref: reject/sale/{sale_id}/',
        )
        self.assertTrue(sticky.is_done)

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
        self.assertEqual(
            DailyNote.objects.filter(content__contains=f'ref: sale_complete/{sale.id}').count(),
            1,
        )

        first.checked_by = self.manager_user
        apply_pending_change(first)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 19)
        note = DailyNote.objects.get(content__contains=f'ref: sale_complete/{sale.id}')
        self.assertEqual(note.board_column, 'past')

    def test_complete_uses_existing_payment_reference_and_handles_push_errors(self):
        from unittest.mock import patch

        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale = Sale.objects.get(pk=created.data['id'])
        sale.status = 'awaiting_payment'
        sale.payment_reference = 'KEEP-ME'
        sale.save(update_fields=['status', 'payment_reference'])
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
        self.assertEqual(holding.amount_paid, Decimal('100.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

    def test_manager_cannot_return_approved_sale(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        manager = self._manager_client()
        approve = manager.post(f'/api/sales/{sale_id}/complete/', {}, format='json')
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        blocked = manager.post(
            f'/api/sales/{sale_id}/reject-complete/',
            {'rejection_reason': 'Send it back'},
            format='json',
        )
        self.assertEqual(blocked.status_code, status.HTTP_404_NOT_FOUND)
        sale = Sale.objects.get(pk=sale_id)
        self.assertEqual(sale.status, 'completed')

    def test_admin_returns_approved_and_posted_sales_for_correction(self):
        created = self.client.post('/api/sales/', self._sale_payload(), format='json')
        sale_id = created.data['id']
        manager = self._manager_client()
        approve = manager.post(f'/api/sales/{sale_id}/complete/', {}, format='json')
        self.assertEqual(approve.status_code, status.HTTP_200_OK)

        admin = self._admin_client()
        returned = admin.post(
            f'/api/sales/{sale_id}/reject-complete/',
            {'rejection_reason': 'Wrong customer'},
            format='json',
        )
        self.assertEqual(returned.status_code, status.HTTP_200_OK, returned.data)
        sale = Sale.objects.get(pk=sale_id)
        self.assertEqual(sale.status, 'holding')
        self.assertTrue(sale_needs_salesperson_action(sale))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

        edited = self.client.post(
            '/api/sales/holding/',
            {
                'holding_id': sale_id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': '2',
                        'unit_price': '100.00',
                    }
                ],
                'client_channel': 'web',
            },
            format='json',
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK, edited.data)
        queued = self.client.post(
            f'/api/sales/{sale_id}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': '200.00',
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(queued.status_code, status.HTTP_201_CREATED, queued.data)
        self.assertEqual(queued.data['status'], 'pending_approval')

        approve = manager.post(f'/api/sales/{sale_id}/complete/', {}, format='json')
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.assertEqual(approve.data['status'], 'completed')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 18)

        posted_return = admin.post(
            f'/api/sales/{sale_id}/reject-complete/',
            {'rejection_reason': 'Reverse and fix'},
            format='json',
        )
        self.assertEqual(posted_return.status_code, status.HTTP_200_OK, posted_return.data)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'holding')
        self.assertTrue(sale_needs_salesperson_action(sale))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertFalse(sale_report_queryset().filter(pk=sale.pk).exists())
        opened = self.client.get(f'/api/sales/{sale_id}/')
        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        self.assertEqual(len(opened.data['items']), 1)
        self.assertEqual(opened.data['items'][0]['product_id'], self.product.id)
