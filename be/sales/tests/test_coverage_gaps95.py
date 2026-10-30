"""Targeted tests to push sales module coverage to >=95%."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from inventory.models import StockLayer, StockMovement
from products.models import Category, Product
from sales.models import (
    Customer,
    CustomerWalletTransaction,
    Sale,
    SaleItem,
    SaleItemLayerAllocation,
)
from sales.refunds import SaleRefundService
from sales.sale_completion_approval import (
    CORRECTION_FINGERPRINT_KEY,
    POSTED_RETURN_BLOCKED_REFUND,
    UNEDITED_RETURN_MESSAGE,
    admin_return_sale_for_correction,
    approve_queued_sale,
    assert_returned_sale_was_edited,
    attach_correction_fingerprint,
    complete_queued_sale,
    pending_sale_complete_change,
    returned_sale_was_edited,
    reverse_sale_wallet_effects,
    sale_correction_fingerprint,
    sale_needs_salesperson_action,
    stored_correction_fingerprint,
    unpost_posted_sale,
)
from sales.sale_debt_sync import (
    _underpaid_sales_with_live_debt,
    apply_settlement_to_underpaid_sales,
    sync_sale_customer_debt,
)
from sales.views import SaleViewSet, _parse_backfill_request_data
from sales.visibility import user_sees_all_debt
from utils.tests.api_test_base import ManagerAPITestCase


class SaleCompletionApprovalGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('sca95_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.admin = User.objects.create_superuser('sca95_admin', 'a@t.com', 'x')
        cls.category = Category.objects.create(name='SCA95', is_active=True)
        cls.track_product = Product.objects.create(
            name='Tracked', sku='SCA95-T', category=cls.category,
            price=Decimal('50'), stock_quantity=5, track_stock=True, is_active=True,
        )
        cls.no_track = Product.objects.create(
            name='Service', sku='SCA95-S', category=cls.category,
            price=Decimal('25'), stock_quantity=0, track_stock=False, is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='SCA95 Cust', phone='0700999001', wallet_balance=Decimal('100'), is_active=True,
        )

    def test_salesperson_action_pending_blocks_rejected_path(self):
        holding = Sale.objects.create(
            cashier=self.manager, status='holding',
            subtotal=Decimal('10'), total=Decimal('10'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(holding.pk),
            entity_repr='H-PEND',
            reason='waiting',
            status=PendingChange.STATUS_PENDING,
        )
        self.assertFalse(sale_needs_salesperson_action(holding))

    def test_correction_fingerprint_normalization_and_edit_check(self):
        sale = Sale.objects.create(
            cashier=self.manager, status='holding',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=sale, product=self.track_product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'),
        )
        change = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr='FP',
            reason='bad',
            status=PendingChange.STATUS_REJECTED,
            original_values={CORRECTION_FINGERPRINT_KEY: 'not-a-dict'},
        )
        self.assertIsNone(stored_correction_fingerprint(sale))

        fp = sale_correction_fingerprint(sale)
        fp['items'] = ['skip-me'] + fp['items']
        change.original_values = {CORRECTION_FINGERPRINT_KEY: fp}
        change.save(update_fields=['original_values'])
        stored = stored_correction_fingerprint(sale)
        self.assertIsNotNone(stored)

        exact = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr='FP-EXACT',
            reason='bad',
            status=PendingChange.STATUS_REJECTED,
            original_values={CORRECTION_FINGERPRINT_KEY: sale_correction_fingerprint(sale)},
        )
        self.assertFalse(returned_sale_was_edited(sale))
        exact.delete()

        attach_correction_fingerprint(change, sale, previous_status='pending_approval')
        change.refresh_from_db()
        self.assertIn('returned_from_status', change.original_values)

        unedited = Sale.objects.create(
            cashier=self.manager, status='holding',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=unedited, product=self.track_product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'),
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(unedited.pk),
            entity_repr='UNEDIT',
            reason='bad',
            status=PendingChange.STATUS_REJECTED,
            rejection_reason='Fix totals',
            original_values={CORRECTION_FINGERPRINT_KEY: sale_correction_fingerprint(unedited)},
        )
        with self.assertRaises(ValidationError) as ctx:
            assert_returned_sale_was_edited(unedited)
        self.assertIn(UNEDITED_RETURN_MESSAGE, str(ctx.exception))
        # Explicit cashier confirm allows sending the sale back unchanged.
        assert_returned_sale_was_edited(unedited, confirm_unchanged=True)

        unedited.total = Decimal('49')
        unedited.save(update_fields=['total'])
        self.assertTrue(returned_sale_was_edited(unedited))

    def test_reverse_wallet_and_unpost_branches(self):
        wallet_sale = Sale.objects.create(
            cashier=self.manager, customer=self.customer, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash', sale_number='SCA95-WALLET',
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='debit', source_type='debt',
            amount=Decimal('0'), balance_after=self.customer.wallet_balance,
            sale=wallet_sale, created_by=self.manager,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='credit', source_type='payment',
            amount=Decimal('20'), balance_after=Decimal('80'),
            sale=wallet_sale, created_by=self.manager,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='debit', source_type='debt',
            amount=Decimal('10'), balance_after=Decimal('70'),
            sale=wallet_sale, created_by=self.manager,
        )
        before = self.customer.wallet_balance
        reverse_sale_wallet_effects(wallet_sale, user=self.admin, reason='return')
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.wallet_balance, before)

        no_customer = Sale.objects.create(
            cashier=self.manager, status='completed',
            subtotal=Decimal('10'), total=Decimal('10'), amount_paid=Decimal('10'),
            payment_method='cash',
        )
        reverse_sale_wallet_effects(no_customer, user=self.admin, reason='noop')

        unpost_sale = Sale.objects.create(
            cashier=self.manager, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash', sale_number='SCA95-UNPOST',
        )
        SaleItem.objects.create(
            sale=unpost_sale, product=self.track_product, quantity=2,
            unit_price=Decimal('25'), subtotal=Decimal('50'), unit_cost=Decimal('10'),
        )
        SaleItem.objects.create(
            sale=unpost_sale, product=self.no_track, quantity=1,
            unit_price=Decimal('25'), subtotal=Decimal('25'),
        )
        with patch('accounting.reversal.reverse_source_documents'):
            unpost_posted_sale(unpost_sale, user=self.admin, reason='fix')
        self.assertTrue(
            StockMovement.objects.filter(
                reference=unpost_sale.sale_number, movement_type='return',
            ).exists()
        )

    def test_admin_return_branches(self):
        refunded = Sale.objects.create(
            cashier=self.manager, customer=self.customer, status='completed',
            subtotal=Decimal('20'), total=Decimal('20'), amount_paid=Decimal('20'),
            payment_method='cash', refund_status='partial',
        )
        with self.assertRaises(ValidationError) as ctx:
            admin_return_sale_for_correction(refunded, user=self.admin, reason='fix')
        self.assertIn(POSTED_RETURN_BLOCKED_REFUND, str(ctx.exception))

        awaiting = Sale.objects.create(
            cashier=self.manager, customer=self.customer, status='awaiting_payment',
            subtotal=Decimal('30'), total=Decimal('30'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        pending = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(awaiting.pk),
            entity_repr='AW-PEND',
            reason='queue',
            status=PendingChange.STATUS_PENDING,
        )
        with patch('sales.sale_completion_approval.notify_sale_returned_for_correction'):
            with patch('sales.sale_completion_approval.record_rejected_sale_complete_change'):
                out = admin_return_sale_for_correction(
                    awaiting, user=self.admin, reason='Wrong payment',
                )
        self.assertEqual(out.status, 'holding')
        pending.refresh_from_db()
        self.assertEqual(pending.status, PendingChange.STATUS_REJECTED)

    def test_approve_and_complete_guardrails(self):
        holding = Sale.objects.create(
            cashier=self.manager, status='holding',
            subtotal=Decimal('25'), total=Decimal('25'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        with self.assertRaises(ValidationError):
            approve_queued_sale(holding, user=self.manager)
        with self.assertRaises(ValidationError):
            complete_queued_sale(holding, self.manager)

        pending = Sale.objects.create(
            cashier=self.manager, customer=self.customer, status='pending_approval',
            subtotal=Decimal('25'), total=Decimal('25'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=pending, product=self.no_track, quantity=1,
            unit_price=Decimal('25'), subtotal=Decimal('25'),
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(pending.pk),
            entity_repr='P-NOTRACK',
            reason='q',
            status=PendingChange.STATUS_PENDING,
            apply_payload={
                'amount_paid': '25',
                'use_wallet': True,
                'wallet_amount_locked': '50',
            },
        )
        self.customer.wallet_balance = Decimal('10')
        self.customer.save(update_fields=['wallet_balance'])
        with self.assertRaises(ValidationError):
            complete_queued_sale(pending, self.manager, pending_sale_complete_change(pending).apply_payload)

        self.customer.wallet_balance = Decimal('100')
        self.customer.save(update_fields=['wallet_balance'])
        with patch('accounting.services.create_sale_journal_entry', side_effect=RuntimeError('books')):
            with patch('agents.push.get_push_notifier', side_effect=RuntimeError('push')):
                complete_queued_sale(
                    pending, self.manager, pending_sale_complete_change(pending).apply_payload,
                )
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'completed')


class RefundLayersAndLimitsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.user = User.objects.create_user('ref95', password='x')
        UserProfile.objects.create(
            user=cls.user, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Ref95', phone='0700999002', wallet_balance=Decimal('-30'), is_active=True,
        )
        cls.product = Product.objects.create(
            name='Layer Ref', sku='REF95-L', price=Decimal('40'), cost=Decimal('15'),
            stock_quantity=10, track_stock=True, is_active=True,
        )

    def test_layers_return_and_wallet_debt_reversal(self):
        sale = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('10'),
            payment_method='cash',
        )
        item = SaleItem.objects.create(
            sale=sale, product=self.product, quantity=2,
            unit_price=Decimal('20'), subtotal=Decimal('40'), unit_cost=Decimal('15'),
        )
        layer = StockLayer.objects.create(
            product=self.product,
            qty_received=10,
            qty_remaining=10,
            unit_cost=Decimal('15'),
            unit_sell_price=Decimal('20'),
            received_at=timezone.now(),
        )
        SaleItemLayerAllocation.objects.create(
            sale_item=item, stock_layer=layer, quantity=2, qty_returned=0,
            unit_cost=Decimal('15'), unit_sell_price=Decimal('20'),
        )
        svc = SaleRefundService()
        with patch('inventory.stock_layers.layers_enabled', return_value=True):
            with patch('inventory.stock_layers.restore_layer_qty') as restore:
                with patch(
                    'accounting.services.create_sale_refund_journal_entry',
                    side_effect=RuntimeError('je'),
                ):
                    refund = svc.create_refund(
                        sale, reason='Layer return', user=self.user,
                        items=[{'sale_item_id': item.id, 'quantity': 1}],
                    )
        restore.assert_called()
        self.assertEqual(refund.amount, Decimal('20'))

        svc._return_stock(
            sale=sale,
            sale_item=item,
            quantity=0,
            branch=None,
            user=self.user,
            reference='noop',
            notes='skip non-track',
        )
        no_track_item = SaleItem.objects.create(
            sale=sale,
            product=Product.objects.create(
                name='NT', sku='REF95-NT', price=Decimal('1'),
                track_stock=False, is_active=True,
            ),
            quantity=1, unit_price=Decimal('1'), subtotal=Decimal('1'),
        )
        svc._return_stock(
            sale=sale, sale_item=no_track_item, quantity=1,
            branch=None, user=self.user, reference='r', notes='n',
        )

    def test_refund_amount_bounds(self):
        sale = Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('10'), total=Decimal('10'), amount_paid=Decimal('10'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=sale, product=self.product, quantity=1,
            unit_price=Decimal('10'), subtotal=Decimal('10'),
        )
        svc = SaleRefundService()
        with patch.object(svc, '_resolve_refund_lines', return_value=[{
            'sale_item': sale.items.first(),
            'quantity': 1,
            'unit_price': Decimal('0'),
            'subtotal': Decimal('0'),
        }]):
            with self.assertRaises(ValidationError):
                svc.create_refund(sale, reason='zero amount', user=self.user, full=True)

        with patch.object(svc, '_resolve_refund_lines', return_value=[{
            'sale_item': sale.items.first(),
            'quantity': 1,
            'unit_price': Decimal('100'),
            'subtotal': Decimal('100'),
        }]):
            with self.assertRaises(ValidationError):
                svc.create_refund(sale, reason='too much', user=self.user, full=True)


class SaleDebtSyncUnderpaidGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.user = User.objects.create_user('debt95', password='x')
        UserProfile.objects.create(
            user=cls.user, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Debt95', phone='0700999003', wallet_balance=Decimal('-500'), is_active=True,
        )

    def test_underpaid_skips_stale_and_settlement_unpaid_zero(self):
        sale_live = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            sale_type='pos', subtotal=Decimal('200'), total=Decimal('200'),
            amount_paid=Decimal('0'), payment_method='cash', sale_number='LIVE-DEBT',
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='debit', source_type='debt',
            amount=Decimal('200'), balance_after=Decimal('-700'),
            sale=sale_live, created_by=self.user,
        )
        targets = _underpaid_sales_with_live_debt(self.customer.pk)
        self.assertEqual(len(targets), 1)

        sale_stale = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            sale_type='pos', subtotal=Decimal('100'), total=Decimal('100'),
            amount_paid=Decimal('0'), payment_method='cash', sale_number='STALE-DEBT',
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='debit', source_type='debt',
            amount=Decimal('100'), balance_after=Decimal('-800'),
            sale=sale_stale, created_by=self.user,
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='credit', source_type='other',
            amount=Decimal('100'), balance_after=Decimal('-700'),
            sale=sale_stale, reference=sale_stale.sale_number,
            notes='Admin returned sale for correction', created_by=self.user,
        )
        targets2 = _underpaid_sales_with_live_debt(self.customer.pk)
        self.assertEqual(len([s for s in targets2 if s.pk == sale_stale.pk]), 0)

        paid_off = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            sale_type='pos', subtotal=Decimal('50'), total=Decimal('50'),
            amount_paid=Decimal('50'), payment_method='cash', sale_number='PAID-DEBT',
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='debit', source_type='debt',
            amount=Decimal('50'), balance_after=Decimal('-750'),
            sale=paid_off, created_by=self.user,
        )
        apply_settlement_to_underpaid_sales(self.customer, Decimal('10'))

        sync_sale = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            sale_type='pos', subtotal=Decimal('80'), total=Decimal('80'),
            amount_paid=Decimal('80'), payment_method='cash', sale_number='SYNC-CLEAR',
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer, transaction_type='debit', source_type='debt',
            amount=Decimal('80'), balance_after=Decimal('-830'),
            sale=sync_sale, created_by=self.user,
        )
        cleared = sync_sale_customer_debt(sync_sale, user=self.user, reason='paid off')
        self.assertEqual(cleared['action'], 'debt_cleared')


class ViewsParseAndCancelTests(ManagerAPITestCase):
    def test_parse_backfill_request_data_flags(self):
        req = MagicMock()
        req.data = {
            'items': '[{"product_id": 1, "quantity": 1}]',
            'customer_id': '',
            'served_by_id': 'null',
            'amount_paid': '10.00',
            'allow_partial_payment': 'yes',
            'acknowledge_stock_warnings': '1',
            'create_invoice': 'true',
        }
        parsed = _parse_backfill_request_data(req)
        self.assertIsInstance(parsed['items'], list)
        self.assertIsNone(parsed['customer_id'])
        self.assertTrue(parsed['allow_partial_payment'])
        self.assertTrue(parsed['create_invoice'])

    def test_cancel_holding_validation_response(self):
        completed = Sale.objects.create(
            cashier=self.manager_user, status='completed',
            subtotal=Decimal('10'), total=Decimal('10'), amount_paid=Decimal('10'),
            payment_method='cash',
        )
        factory = APIRequestFactory()
        view = SaleViewSet.as_view({'post': 'cancel_holding'})
        req = factory.post(f'/api/sales/{completed.id}/cancel-holding/')
        force_authenticate(req, user=self.manager_user)
        resp = view(req, pk=completed.pk)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class VisibilityDebtPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.cashier = User.objects.create_user('vis95', password='x')
        profile = UserProfile.objects.create(
            user=cls.cashier, role='cashier', custom_role=roles[ROLE_SALES], is_active=True,
        )
        cls.profile = profile

    def test_debt_update_permission_sees_all_debt(self):
        with patch.object(self.profile, 'has_permission', return_value=True):
            self.assertTrue(user_sees_all_debt(self.cashier))
        with patch.object(self.profile, 'has_permission', side_effect=RuntimeError('perm')):
            self.assertFalse(user_sees_all_debt(self.cashier))
