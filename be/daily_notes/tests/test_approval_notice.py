"""Daily notes notices when an approval is returned to the requester."""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from daily_notes.approval_notice import (
    SOURCE_PENDING_CHANGE,
    action_label,
    build_rejection_notice,
    build_sale_approved_notice,
    notify_approval_rejected,
    notify_sale_approved,
)
from daily_notes.models import DailyNote, DailyTask


class ApprovalNoticeTests(TestCase):
    def setUp(self):
        self.maker = User.objects.create_user(
            'maker', password='x', first_name='Ann', last_name='Cash'
        )
        self.checker = User.objects.create_user(
            'checker', password='x', first_name='Bea', last_name='Mgr'
        )

    def test_action_label_known_and_fallback(self):
        self.assertEqual(action_label('sale_refund'), 'sale void / refund')
        self.assertEqual(action_label('custom_thing'), 'custom thing')
        self.assertEqual(action_label(''), 'request')
        self.assertEqual(action_label(None), 'request')

    def test_build_rejection_notice_includes_footer(self):
        title, content = build_rejection_notice(
            action_type='sale_rollback',
            entity_repr='SALE-9',
            rejection_reason='Wrong till',
            checker=self.checker,
            source=SOURCE_PENDING_CHANGE,
            record_id=42,
        )
        self.assertEqual(title, 'Approval rejected: sale rollback')
        self.assertIn('Bea Mgr returned your sale rollback for SALE-9', content)
        self.assertIn('Reason: Wrong till', content)
        self.assertIn('source: pending_change', content)
        self.assertIn('id: 42', content)

    def test_notify_writes_note_and_task_for_requester(self):
        result = notify_approval_rejected(
            requester=self.maker,
            checker=self.checker,
            action_type='product_price',
            entity_repr='Sugar 2kg',
            rejection_reason='Too low',
            source=SOURCE_PENDING_CHANGE,
            record_id=7,
        )
        self.assertIsNotNone(result)
        note, task = result
        self.assertEqual(note.author_id, self.maker.id)
        self.assertEqual(note.note_date, date.today())
        self.assertIn('Sugar 2kg', note.content)
        self.assertEqual(task.assigned_to_id, self.maker.id)
        self.assertEqual(task.author_id, self.checker.id)
        self.assertFalse(task.is_done)
        self.assertEqual(DailyNote.objects.filter(author=self.maker).count(), 1)
        self.assertEqual(DailyTask.objects.filter(assigned_to=self.maker).count(), 1)

    def test_notify_skips_missing_requester_or_id(self):
        self.assertIsNone(
            notify_approval_rejected(
                requester=None,
                checker=self.checker,
                action_type='expense',
                record_id=1,
            )
        )
        self.assertIsNone(
            notify_approval_rejected(
                requester=self.maker,
                checker=self.checker,
                action_type='expense',
                record_id=None,
            )
        )
        self.assertEqual(DailyNote.objects.count(), 0)

    def test_notice_uses_username_when_no_full_name(self):
        bare = User.objects.create_user('bare_checker', password='x')
        title, content = build_rejection_notice(
            action_type='expense',
            entity_repr='',
            rejection_reason='',
            checker=bare,
            source='expense',
            record_id=3,
        )
        self.assertIn('bare_checker returned your expense for your request', content)
        self.assertIn('Reason: No reason given', content)
        self.assertTrue(title.startswith('Approval rejected'))

    def test_sale_complete_label_and_approved_notice(self):
        self.assertEqual(action_label('sale_complete'), 'sale completion')
        self.assertEqual(action_label('debt_collection'), 'debt collection')
        title, content = build_sale_approved_notice(
            sale_number='S-99', checker=self.checker
        )
        self.assertIn('S-99', title)
        self.assertIn('You can issue the receipt now', content)
        self.assertIn('Bea Mgr', content)

        class FakeSale:
            cashier = self.maker
            sale_number = 'S-100'
            pk = 100

        notify_sale_approved(sale=FakeSale(), checker=self.checker)
        self.assertTrue(
            DailyNote.objects.filter(author=self.maker, title__icontains='S-100').exists()
        )
        self.assertTrue(
            DailyTask.objects.filter(assigned_to=self.maker, title__icontains='S-100').exists()
        )
        self.assertIsNone(notify_sale_approved(sale=type('S', (), {'cashier': None, 'sale_number': 'x'})(), checker=self.checker))
        title, content = build_sale_approved_notice(sale_number='', checker=None)
        self.assertIn('this sale', title)
        self.assertIn('A reviewer', content)

    def test_notice_writers_swallow_errors(self):
        from unittest.mock import patch

        class FakeSale:
            cashier = self.maker
            sale_number = 'S-ERR'
            pk = 7

        with patch(
            'daily_notes.approval_notice.DailyNote.objects.create',
            side_effect=RuntimeError('db'),
        ):
            self.assertIsNone(
                notify_approval_rejected(
                    requester=self.maker,
                    checker=self.checker,
                    action_type='sale_complete',
                    entity_repr='S-ERR',
                    rejection_reason='x',
                    source=SOURCE_PENDING_CHANGE,
                    record_id=7,
                )
            )
            self.assertIsNone(notify_sale_approved(sale=FakeSale(), checker=self.checker))
