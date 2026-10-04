"""Approval cards leave To do once the request has been approved, resubmitted or cancelled."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from approvals.models import PendingChange
from approvals.service import _apply_single_change, reject_change, resubmit_change
from daily_notes.approval_notice import (
    SOURCE_EXPENSE,
    SOURCE_PENDING_CHANGE,
    SOURCE_SALE_BACKFILL,
    SOURCE_SALE_COMPLETE,
    complete_backfill_return_notes,
    complete_manager_queue_notes,
    complete_requester_notices_for_change,
    complete_sale_return_notes,
    complete_stale_approval_notices,
    notify_approval_rejected,
    notify_managers_sale_queued,
    notify_sale_approved,
)
from daily_notes.models import DailyNote, DailyTask
from daily_notes.services import DailyNoteService, DailyTaskService
from sales.models import Sale


def _open_notes(**filters):
    return DailyNote.objects.filter(is_done=False, **filters)


def _open_tasks(**filters):
    return DailyTask.objects.filter(is_done=False, **filters)


class ApprovalNoticeClearingTests(TestCase):
    def setUp(self):
        self.maker = User.objects.create_user('clear_maker', password='x')
        self.manager = User.objects.create_user('clear_mgr', password='x')
        self.admin = User.objects.create_superuser('clear_admin', 'a@t.com', 'x')
        self.today = timezone.localdate()

    def _sale(self, number, status='pending_approval'):
        return Sale.objects.create(
            sale_number=number,
            status=status,
            cashier=self.maker,
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
        )

    def _queue_card(self, source, record_id):
        with patch(
            'daily_notes.approval_notice.manager_notice_recipients',
            return_value=[self.manager],
        ):
            return notify_managers_sale_queued(
                author=self.maker, source=source, record_id=record_id,
                entity_repr=f'S-{record_id}',
            )

    def _change(self, action_type='product_price', status=PendingChange.STATUS_PENDING):
        return PendingChange.objects.create(
            action_type=action_type,
            entity_type='products.Product',
            entity_id='1',
            entity_repr='Soap',
            reason='price',
            status=status,
            made_by=self.maker,
        )

    def test_similar_sale_ids_do_not_clear_each_other(self):
        self._queue_card(SOURCE_SALE_COMPLETE, 15)
        self._queue_card(SOURCE_SALE_COMPLETE, 150)
        self.assertEqual(complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=15), 1)
        self.assertTrue(_open_notes(content__contains='ref: sale_complete/150/').exists())
        self.assertFalse(_open_notes(content__contains='ref: sale_complete/15/').exists())

    def test_requeue_reopens_own_card_not_a_similar_one(self):
        self._queue_card(SOURCE_SALE_COMPLETE, 7)
        complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=7)
        self._queue_card(SOURCE_SALE_COMPLETE, 70)
        reopened = self._queue_card(SOURCE_SALE_COMPLETE, 7)
        self.assertEqual(len(reopened), 1)
        self.assertIn('ref: sale_complete/7/', reopened[0].content)
        self.assertEqual(_open_notes(content__contains='ref: sale_complete/7').count(), 2)

    def test_legacy_card_without_trailing_slash_still_matches_exact_id(self):
        old = DailyNote.objects.create(
            note_date=self.today, title='Clear and move: S-3', author=self.manager,
            assigned_to=self.manager, content='old card\n---\nref: sale_complete/3',
        )
        other = DailyNote.objects.create(
            note_date=self.today, title='Clear and move: S-30', author=self.manager,
            assigned_to=self.manager, content='old card\n---\nref: sale_complete/30',
        )
        complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=3)
        old.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(old.is_done)
        self.assertFalse(other.is_done)

    def test_sale_approved_notice_goes_straight_to_past(self):
        sale = self._sale('S-APPROVED', status='completed')
        note = notify_sale_approved(sale=sale, checker=self.manager)
        self.assertTrue(note.is_done)
        self.assertEqual(note.board_column, 'past')

    def test_pending_change_rejection_clears_on_resubmit(self):
        change = self._change()
        reject_change(change, self.admin, 'Too high')
        self.assertTrue(_open_notes(author=self.maker).exists())
        self.assertTrue(_open_tasks(assigned_to=self.maker).exists())
        resubmit_change(change, self.maker)
        self.assertFalse(_open_notes(author=self.maker).exists())
        self.assertFalse(_open_tasks(assigned_to=self.maker).exists())

    def test_pending_change_rejection_clears_when_approved(self):
        change = self._change()
        reject_change(change, self.admin, 'Too high')
        PendingChange.objects.filter(pk=change.pk).update(status=PendingChange.STATUS_PENDING)
        change.refresh_from_db()
        with patch('approvals.apply.apply_pending_change'):
            _apply_single_change(change, self.admin, None)
        self.assertFalse(_open_notes(author=self.maker).exists())
        self.assertFalse(_open_tasks(assigned_to=self.maker).exists())

    def test_rejection_for_other_change_is_left_alone(self):
        first = self._change()
        second = self._change()
        reject_change(first, self.admin, 'No')
        reject_change(second, self.admin, 'No')
        complete_requester_notices_for_change(first)
        self.assertEqual(_open_notes(author=self.maker).count(), 1)
        self.assertIn(f'id: {second.id}', _open_notes(author=self.maker).get().content)

    def test_backfill_return_does_not_touch_sale_with_same_id(self):
        sale_note = DailyNote.objects.create(
            note_date=self.today, title='Approval rejected: sale completion',
            author=self.manager, assigned_to=self.maker, is_sticky=True,
            content='x\nsale_id: 4\nref: reject/sale/4/',
        )
        legacy_backfill = DailyNote.objects.create(
            note_date=self.today, title='Approval rejected: past sale entry',
            author=self.manager, assigned_to=self.maker, is_sticky=True,
            content='x\nsource: pending_change\nid: 4\nref: reject/sale/4/',
        )
        complete_sale_return_notes(record_id=4)
        sale_note.refresh_from_db()
        legacy_backfill.refresh_from_db()
        self.assertTrue(sale_note.is_done)
        self.assertFalse(legacy_backfill.is_done)
        complete_backfill_return_notes(change_id=4)
        legacy_backfill.refresh_from_db()
        self.assertTrue(legacy_backfill.is_done)

    def test_backfill_rejection_clears_on_resubmit(self):
        change = self._change(action_type='sale_backfill', status=PendingChange.STATUS_REJECTED)
        notify_approval_rejected(
            requester=self.maker, checker=self.manager, action_type='sale_backfill',
            entity_repr='Past sale', rejection_reason='Dates', source=SOURCE_PENDING_CHANGE,
            record_id=change.id, is_sticky=True,
        )
        self.assertTrue(_open_notes(assigned_to=self.maker, is_sticky=True).exists())
        complete_requester_notices_for_change(change)
        self.assertFalse(_open_notes(assigned_to=self.maker).exists())
        self.assertFalse(_open_tasks(assigned_to=self.maker).exists())

    def test_stale_sweep_closes_resolved_cards_and_keeps_live_ones(self):
        approved = self._sale('S-SWEEP-DONE', status='completed')
        waiting = self._sale('S-SWEEP-WAIT')
        returned = self._sale('S-SWEEP-BACK', status='holding')
        resubmitted = self._sale('S-SWEEP-AGAIN')
        backfill_waiting = self._change(action_type='sale_backfill')
        backfill_done = self._change(action_type='sale_backfill', status=PendingChange.STATUS_APPROVED)
        change_rejected = self._change(status=PendingChange.STATUS_REJECTED)
        change_back = self._change(status=PendingChange.STATUS_PENDING)

        def card(content, **extra):
            return DailyNote.objects.create(
                note_date=self.today, title=extra.pop('title', 'card'),
                author=extra.pop('author', self.manager),
                assigned_to=extra.pop('assigned_to', self.manager),
                content=content, **extra,
            )

        resolved = [
            card(f'ref: sale_complete/{approved.pk}'),
            card(f'ref: sale_backfill/{backfill_done.pk}/'),
            card(f'x\nsale_id: {resubmitted.pk}\nref: reject/sale/{resubmitted.pk}/',
                 assigned_to=self.maker, is_sticky=True),
            card(f'ref: approve/sale/{approved.pk}/', title='Sale #S-SWEEP-DONE was approved',
                 author=self.maker, assigned_to=None),
            card(f'Reason: x\n---\nsource: pending_change\nid: {change_back.pk}',
                 author=self.maker, assigned_to=None),
            card('ref: reject/sale/999999/', assigned_to=self.maker, is_sticky=True),
        ]
        live = [
            card(f'ref: sale_complete/{waiting.pk}/'),
            card(f'ref: sale_backfill/{backfill_waiting.pk}/'),
            card(f'x\nsale_id: {returned.pk}\nref: reject/sale/{returned.pk}/',
                 assigned_to=self.maker, is_sticky=True),
            card(f'Reason: x\n---\nsource: pending_change\nid: {change_rejected.pk}',
                 author=self.maker, assigned_to=None),
            card('Remember to count the till', title='Till'),
        ]
        task = DailyTask.objects.create(
            task_date=self.today, title='Clear and move: S-SWEEP-DONE',
            description=f'ref: sale_complete/{approved.pk}/',
            author=self.manager, assigned_to=self.manager,
        )

        self.assertEqual(complete_stale_approval_notices(), len(resolved) + 1)
        for note in resolved:
            note.refresh_from_db()
            self.assertTrue(note.is_done, note.content)
        for note in live:
            note.refresh_from_db()
            self.assertFalse(note.is_done, note.content)
        task.refresh_from_db()
        self.assertTrue(task.is_done)

    def test_listing_notes_clears_stale_cards(self):
        approved = self._sale('S-LIST-DONE', status='completed')
        note = DailyNote.objects.create(
            note_date=self.today, title='Clear and move: S-LIST-DONE',
            author=self.manager, assigned_to=self.manager,
            content=f'ref: sale_complete/{approved.pk}/',
        )
        list(DailyNoteService().build_queryset(user=self.manager, view_all=False))
        note.refresh_from_db()
        self.assertTrue(note.is_done)

        sticky = DailyNote.objects.create(
            note_date=self.today, title='Approval rejected: sale completion',
            author=self.manager, assigned_to=self.maker, is_sticky=True,
            content=f'x\nsale_id: {approved.pk}\nref: reject/sale/{approved.pk}/',
        )
        blocking = list(DailyNoteService().blocking_for_user(user=self.maker))
        self.assertNotIn(sticky.pk, [n.pk for n in blocking])

        other_user_task = DailyTask.objects.create(
            task_date=self.today, title='Clear and move: S-LIST-DONE',
            description=f'ref: sale_complete/{approved.pk}/',
            author=self.maker, assigned_to=self.maker,
        )
        list(DailyTaskService().build_queryset(user=self.manager, view_all=True))
        other_user_task.refresh_from_db()
        self.assertTrue(other_user_task.is_done)

    def test_missing_ids_and_already_done_items_are_ignored(self):
        from daily_notes.approval_notice import (
            _complete_open_tasks,
            _matching,
            _move_notes_to_past,
            complete_rejection_notices,
        )

        self.assertEqual(_matching(DailyNote.objects.all(), 'content', 'ref: x/', None), [])
        self.assertEqual(complete_sale_return_notes(record_id=None), 0)
        self.assertEqual(complete_backfill_return_notes(change_id=None), 0)
        self.assertEqual(complete_rejection_notices(source=SOURCE_EXPENSE, record_id=None), 0)
        done_note = DailyNote.objects.create(
            note_date=self.today, content='x', author=self.maker, is_done=True,
        )
        done_task = DailyTask.objects.create(
            task_date=self.today, title='t', author=self.maker, assigned_to=self.maker,
            is_done=True,
        )
        self.assertEqual(_move_notes_to_past([done_note]), 0)
        self.assertEqual(_complete_open_tasks([done_task]), 0)
        open_task = DailyTask.objects.create(
            task_date=self.today, title='t', author=self.maker, assigned_to=self.maker,
        )
        with patch.object(DailyTask, 'mark_done', side_effect=RuntimeError('db')):
            self.assertEqual(_complete_open_tasks([open_task]), 0)

    def test_sweep_handles_legacy_backfill_and_unknown_refs(self):
        rejected = self._change(action_type='sale_backfill', status=PendingChange.STATUS_REJECTED)
        resubmitted = self._change(action_type='sale_backfill')
        still_rejected = DailyNote.objects.create(
            note_date=self.today, title='Approval rejected: past sale entry',
            author=self.manager, assigned_to=self.maker, is_sticky=True,
            content=f'x\nref: reject/sale/{rejected.pk}/',
        )
        fixed = DailyNote.objects.create(
            note_date=self.today, title='Approval rejected: past sale entry',
            author=self.manager, assigned_to=self.maker, is_sticky=True,
            content=f'x\nref: reject/sale/{resubmitted.pk}/',
        )
        unknown = DailyNote.objects.create(
            note_date=self.today, title='Link', author=self.maker,
            content='see ref: wiki/12',
        )
        complete_stale_approval_notices()
        for note in (still_rejected, fixed, unknown):
            note.refresh_from_db()
        self.assertFalse(still_rejected.is_done)
        self.assertTrue(fixed.is_done)
        self.assertFalse(unknown.is_done)

    def test_sweep_survives_a_broken_card(self):
        DailyNote.objects.create(
            note_date=self.today, title='card', author=self.manager,
            content='ref: sale_complete/1/',
        )
        DailyTask.objects.create(
            task_date=self.today, title='card', author=self.manager,
            assigned_to=self.manager, description='ref: sale_complete/1/',
        )
        with patch(
            'daily_notes.approval_notice._notice_is_resolved', side_effect=RuntimeError('db'),
        ):
            self.assertEqual(complete_stale_approval_notices(), 0)

    def test_backfill_queue_card_clears_by_change_id(self):
        self._queue_card(SOURCE_SALE_BACKFILL, 21)
        self._queue_card(SOURCE_SALE_BACKFILL, 210)
        complete_manager_queue_notes(source=SOURCE_SALE_BACKFILL, record_id=21)
        self.assertEqual(_open_notes(content__contains='ref: sale_backfill/').count(), 1)


class FinancialRejectionClearingTests(TestCase):
    def setUp(self):
        from settings.test_utils import disable_maker_checker

        disable_maker_checker()
        self.maker = User.objects.create_user('fin_maker', password='x')
        self.checker = User.objects.create_user('fin_checker', password='x')
        self.today = timezone.localdate()

    def _assert_cleared(self):
        self.assertFalse(_open_notes(author=self.maker).exists())
        self.assertFalse(_open_tasks(assigned_to=self.maker).exists())

    def _assert_open(self):
        self.assertTrue(_open_notes(author=self.maker).exists())
        self.assertTrue(_open_tasks(assigned_to=self.maker).exists())

    def _expense(self):
        from expenses.models import Expense, ExpenseCategory

        category = ExpenseCategory.objects.create(name='Rent', is_active=True)
        return Expense.objects.create(
            category=category, description='Rent', amount=Decimal('100'),
            expense_date=self.today, status='pending', created_by=self.maker,
        )

    def _income(self):
        from income.models import Income, IncomeCategory

        category = IncomeCategory.objects.create(name='Other', is_active=True)
        return Income.objects.create(
            category=category, description='Tips', amount=Decimal('50'),
            income_date=self.today, status='pending', created_by=self.maker,
        )

    def _transfer(self):
        from bankaccounts.models import BankAccount
        from transfers.models import MoneyTransfer

        def account(number):
            return BankAccount.objects.create(
                account_name=number, account_number=number, bank_name='Bank',
                opening_balance=Decimal('1000'), current_balance=Decimal('1000'),
                created_by=self.maker,
            )

        return MoneyTransfer.objects.create(
            transfer_type='bank_to_bank', from_account=account('A-1'),
            to_account=account('A-2'), amount=Decimal('10'), transfer_date=self.today,
            status='pending', description='Float', created_by=self.maker,
        )

    def test_expense_rejection_clears_on_resubmit(self):
        from expenses.services import ExpenseService

        service = ExpenseService()
        expense = self._expense()
        service.reject_expense(expense, self.checker, 'Receipt missing')
        self._assert_open()
        service.resubmit_expense(expense, self.maker)
        self._assert_cleared()

    def test_expense_rejection_clears_when_approved(self):
        from expenses.services import ExpenseService

        service = ExpenseService()
        expense = self._expense()
        service.reject_expense(expense, self.checker, 'Receipt missing')
        expense.status = 'pending'
        expense.save(update_fields=['status'])
        service.approve_expense(expense, self.checker)
        self._assert_cleared()

    def test_income_rejection_clears_on_resubmit_and_approve(self):
        from income.services import IncomeService

        service = IncomeService()
        income = self._income()
        service.reject_income(income, self.checker, 'Wrong date')
        self._assert_open()
        service.resubmit_income(income, self.maker)
        self._assert_cleared()
        service.reject_income(income, self.checker, 'Still wrong')
        self._assert_open()
        income.status = 'pending'
        income.save(update_fields=['status'])
        service.approve_income(income, self.checker)
        self._assert_cleared()

    def test_transfer_rejection_clears_on_resubmit_and_approve(self):
        from transfers.services import MoneyTransferService

        service = MoneyTransferService()
        transfer = self._transfer()
        service.reject_transfer(transfer, self.checker, 'Wrong account')
        self._assert_open()
        service.resubmit_transfer(transfer, self.maker)
        self._assert_cleared()
        service.reject_transfer(transfer, self.checker, 'Again')
        self._assert_open()
        transfer.status = 'pending'
        transfer.save(update_fields=['status'])
        service.approve_transfer(transfer, self.checker)
        self._assert_cleared()

    def test_sweep_clears_legacy_expense_notice_once_approved(self):
        expense = self._expense()
        note = DailyNote.objects.create(
            note_date=self.today, title='Approval rejected: expense', author=self.maker,
            content=f'Reason: x\n---\nsource: {SOURCE_EXPENSE}\nid: {expense.pk}',
        )
        expense.status = 'rejected'
        expense.save(update_fields=['status'])
        complete_stale_approval_notices(user=self.maker)
        note.refresh_from_db()
        self.assertFalse(note.is_done)
        expense.status = 'approved'
        expense.save(update_fields=['status'])
        complete_stale_approval_notices(user=self.maker)
        note.refresh_from_db()
        self.assertTrue(note.is_done)
