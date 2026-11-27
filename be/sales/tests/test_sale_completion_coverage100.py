"""Close remaining sale_completion_approval.py coverage gaps to 100%."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund
from sales.sale_completion_approval import (
    DISCARD_HAS_REFUNDS,
    DISCARD_NOT_ALLOWED,
    DISCARD_REASON_REQUIRED,
    complete_queued_sale,
    discard_returned_sale,
    ensure_sale_openable_for_pos_correction,
    sale_can_be_permanently_discarded,
    sale_must_requeue_after_correction,
    unpost_posted_sale,
)
from sales.services import SaleService


class SaleCompletionCoverage100Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('sca100_admin', password='x', is_staff=True)
        cls.cashier = User.objects.create_user('sca100_cashier', password='x')
        cat = Category.objects.create(name='SCA100', is_active=True)
        cls.product = Product.objects.create(
            name='SCA100 Item',
            sku='SCA100-1',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=30,
            track_stock=True,
            is_active=True,
        )

    def test_sale_can_be_permanently_discarded_edge_cases(self):
        self.assertFalse(sale_can_be_permanently_discarded(None))
        bare = Sale(status='completed')
        self.assertFalse(sale_can_be_permanently_discarded(bare))

        sale = Sale.objects.create(
            sale_number='S-SCA100-DISC',
            status='holding',
            cashier=self.cashier,
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            refund_status='partial',
        )
        self.assertFalse(sale_can_be_permanently_discarded(sale))

        sale.refund_status = 'none'
        sale.save(update_fields=['refund_status'])
        SaleRefund.objects.create(
            sale=sale,
            refund_type='full',
            amount=Decimal('10'),
            reason='prior',
            refunded_by=self.admin,
        )
        self.assertFalse(sale_can_be_permanently_discarded(sale))

    def test_discard_returned_sale_validation_branches(self):
        sale = Sale.objects.create(
            sale_number='S-SCA100-DISCARD',
            status='holding',
            cashier=self.cashier,
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('0'),
            payment_method='cash',
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            reason='return',
            status=PendingChange.STATUS_REJECTED,
            original_values={'returned_from_status': 'completed'},
        )
        with self.assertRaises(ValidationError) as blank:
            discard_returned_sale(
                sale, user=self.admin, reason='   ', confirm=True,
                confirm_sale_number=sale.sale_number,
            )
        self.assertIn(str(DISCARD_REASON_REQUIRED), str(blank.exception))

        completed = Sale.objects.create(
            sale_number='S-SCA100-DONE',
            status='completed',
            cashier=self.cashier,
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('50'),
            payment_method='cash',
        )
        with self.assertRaises(ValidationError) as not_allowed:
            discard_returned_sale(
                completed, user=self.admin, reason='Nope', confirm=True,
                confirm_sale_number=completed.sale_number,
            )
        self.assertIn(str(DISCARD_NOT_ALLOWED), str(not_allowed.exception))

        holding = Sale.objects.create(
            sale_number='S-SCA100-REF',
            status='holding',
            cashier=self.cashier,
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('0'),
            payment_method='cash',
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(holding.pk),
            entity_repr=holding.sale_number,
            reason='return',
            status=PendingChange.STATUS_REJECTED,
            original_values={'returned_from_status': 'completed'},
        )
        SaleRefund.objects.create(
            sale=holding,
            refund_type='partial',
            amount=Decimal('5'),
            reason='old',
            refunded_by=self.admin,
        )
        with patch(
            'sales.sale_completion_approval.sale_can_be_permanently_discarded',
            return_value=True,
        ):
            with self.assertRaises(ValidationError) as has_refunds:
                discard_returned_sale(
                    holding, user=self.admin, reason='Clear it', confirm=True,
                    confirm_sale_number=holding.sale_number,
                )
        self.assertIn(str(DISCARD_HAS_REFUNDS), str(has_refunds.exception))

    def test_ensure_openable_heals_rejected_pending_approval(self):
        sale = Sale.objects.create(
            sale_number='S-SCA100-HEAL',
            status='pending_approval',
            cashier=self.cashier,
            subtotal=Decimal('40'),
            total=Decimal('40'),
            amount_paid=Decimal('0'),
            payment_method='cash',
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            reason='queue',
            status=PendingChange.STATUS_REJECTED,
            made_by=self.cashier,
        )
        healed = ensure_sale_openable_for_pos_correction(sale)
        self.assertEqual(healed.status, 'holding')

    def test_ensure_openable_rejects_completed_sale(self):
        sale = Sale.objects.create(
            sale_number='S-SCA100-DONE2',
            status='completed',
            cashier=self.cashier,
            subtotal=Decimal('40'),
            total=Decimal('40'),
            amount_paid=Decimal('40'),
            payment_method='cash',
        )
        with self.assertRaises(ValidationError):
            ensure_sale_openable_for_pos_correction(sale)

    def test_sale_must_requeue_delegates_to_needs_salesperson_action(self):
        sale = Sale.objects.create(
            sale_number='S-SCA100-REQUEUE',
            status='holding',
            cashier=self.cashier,
            subtotal=Decimal('40'),
            total=Decimal('40'),
            amount_paid=Decimal('0'),
            payment_method='cash',
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            reason='return',
            status=PendingChange.STATUS_REJECTED,
            made_by=self.cashier,
            original_values={'returned_from_status': 'completed'},
        )
        self.assertTrue(sale_must_requeue_after_correction(sale))

    def test_unpost_skips_fully_refunded_line(self):
        sale = Sale.objects.create(
            sale_number='S-SCA100-UNPOST',
            status='completed',
            cashier=self.cashier,
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('100'),
            payment_method='cash',
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            unit_cost=Decimal('40'),
            subtotal=Decimal('100'),
        )
        refund = SaleRefund.objects.create(
            sale=sale,
            refund_type='full',
            amount=Decimal('100'),
            reason='full',
            refunded_by=self.admin,
        )
        from sales.models import SaleRefundItem

        SaleRefundItem.objects.create(
            refund=refund,
            sale_item=item,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            subtotal=Decimal('100'),
        )
        with patch('accounting.reversal.reverse_source_documents'):
            unpost_posted_sale(sale, user=self.admin, reason='coverage')

    def _fake_payment(self):
        return {
            'amount_paid': Decimal('100'),
            'change': Decimal('0'),
            'wallet_used': Decimal('0'),
            'payment_status': 'paid',
        }

    def test_complete_queued_stamps_missing_unit_cost_and_skips_field_load(self):
        sale = Sale.objects.create(
            sale_number='S-SCA100-FIELD',
            status='pending_approval',
            cashier=self.cashier,
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('100'),
            payment_method='cash',
            entry_source='field_load',
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            unit_cost=None,
            subtotal=Decimal('100'),
        )
        with patch.object(SaleService, 'validate_sale_items', return_value=[{
            'product': self.product,
            'variant': None,
            'quantity': 1,
            'unit_price': Decimal('100'),
            'unit_cost': Decimal('40'),
            'subtotal': Decimal('100'),
        }]):
            with patch.object(
                SaleService, '_prepare_sale_payment', return_value=self._fake_payment(),
            ):
                with patch.object(SaleService, '_apply_sale_payment'):
                    with patch.object(SaleService, '_create_sale_stock_movements') as move:
                        with patch('accounting.services.create_sale_journal_entry'):
                            with patch(
                                'daily_notes.approval_notice.complete_sale_approved_notices',
                            ):
                                complete_queued_sale(
                                    sale,
                                    self.admin,
                                    {
                                        'payment_method': 'cash',
                                        'amount_paid': '100',
                                        'allow_partial': False,
                                    },
                                )
        move.assert_not_called()
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'completed')
        self.assertEqual(sale.items.first().unit_cost, Decimal('40'))

    def test_complete_queued_backfill_skips_stock_when_checkpoint_says_so(self):
        sale = Sale.objects.create(
            sale_number='S-SCA100-BACK',
            status='pending_approval',
            cashier=self.cashier,
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('100'),
            payment_method='cash',
            entry_source='backfill',
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            unit_cost=Decimal('0'),
            subtotal=Decimal('100'),
        )
        with patch.object(SaleService, 'validate_sale_items', return_value=[]):
            with patch(
                'inventory.checkpoint_services.should_skip_stock_for_past_sale',
                return_value=True,
            ):
                with patch(
                    'sales.sale_completion_approval.sellable_unit_cost',
                    return_value=Decimal('40'),
                ) as cost_fn:
                    with patch.object(
                        SaleService,
                        '_prepare_sale_payment',
                        return_value=self._fake_payment(),
                    ):
                        with patch.object(SaleService, '_apply_sale_payment'):
                            with patch.object(
                                SaleService, '_create_sale_stock_movements',
                            ) as move:
                                with patch('accounting.services.create_sale_journal_entry'):
                                    with patch(
                                        'daily_notes.approval_notice.complete_sale_approved_notices',
                                    ):
                                        complete_queued_sale(
                                            sale,
                                            self.admin,
                                            {
                                                'payment_method': 'cash',
                                                'amount_paid': '100',
                                            },
                                        )
        cost_fn.assert_called()
        move.assert_not_called()
        self.assertEqual(sale.items.first().unit_cost, Decimal('40'))