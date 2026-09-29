"""Daily notes notices when an approval is returned to the requester."""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from daily_notes.approval_notice import (
    SOURCE_PENDING_CHANGE,
    SOURCE_SALE_BACKFILL,
    SOURCE_SALE_COMPLETE,
    action_label,
    build_manager_sale_queue_notice,
    build_rejection_notice,
    build_sale_approved_notice,
    complete_manager_notes_for_change,
    complete_manager_queue_notes,
    complete_sale_return_notes,
    manager_notice_recipients,
    notify_approval_rejected,
    notify_managers_for_change,
    notify_managers_sale_queued,
    notify_sale_approved,
    sale_queue_notice_fingerprint,
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

    def test_sale_complete_rejection_notice_is_sticky_with_comment(self):
        class FakeSale:
            pk = 99
            customer_name = 'Jane Buyer'
            customer = None

        title, content = build_rejection_notice(
            action_type='sale_complete',
            entity_repr='SALE-22',
            rejection_reason='Wrong prices',
            checker=self.checker,
            source=SOURCE_PENDING_CHANGE,
            record_id=42,
            sale=FakeSale(),
        )
        self.assertTrue(title.startswith('Approval rejected'))
        self.assertIn('returned sale SALE-22 for Jane Buyer', content)
        self.assertIn('Their comment:\nWrong prices', content)
        self.assertIn('sale_id: 99', content)
        self.assertIn('ref: reject/sale/99', content)
        self.assertIn('POS cart', content)

        result = notify_approval_rejected(
            requester=self.maker,
            checker=self.checker,
            action_type='sale_complete',
            entity_repr='SALE-22',
            rejection_reason='Wrong prices',
            source=SOURCE_PENDING_CHANGE,
            record_id=42,
            sale=FakeSale(),
        )
        note, task = result
        self.assertTrue(note.is_sticky)
        self.assertEqual(note.assigned_to_id, self.maker.id)
        self.assertEqual(note.author_id, self.checker.id)
        self.assertEqual(task.assigned_to_id, self.maker.id)

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
        self.assertFalse(note.is_sticky)
        self.assertIsNone(note.assigned_to_id)
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
        self.assertIn('Collect payment to complete it', content)
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
        class NamedCustomer:
            name = 'Acme Ltd'

        title, content = build_rejection_notice(
            action_type='sale_backfill',
            entity_repr='Past sale',
            rejection_reason='Dates off',
            checker=self.checker,
            source=SOURCE_SALE_BACKFILL,
            record_id=12,
            sale=type('S', (), {'pk': None, 'customer_name': '', 'customer': NamedCustomer()})(),
        )
        self.assertIn('ref: reject/sale/12/', content)
        title, content = build_rejection_notice(
            action_type='sale_complete',
            entity_repr='',
            rejection_reason='x',
            checker=self.checker,
            source=SOURCE_PENDING_CHANGE,
            record_id=1,
            sale=type('S', (), {'pk': 8, 'customer_name': '  ', 'customer': None})(),
        )
        self.assertIn('walk-in customer', content)
        self.assertIn('this sale', content)

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


class ManagerSaleQueueNoticeTests(TestCase):
    def setUp(self):
        from accounts.models import Role, UserProfile
        from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, sync_default_roles

        sync_default_roles()
        self.sales = User.objects.create_user(
            'queue_sales', password='x', first_name='Ann', last_name='Cash'
        )
        self.manager = User.objects.create_user(
            'queue_mgr', password='x', first_name='Bea', last_name='Mgr'
        )
        UserProfile.objects.create(
            user=self.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )

    def test_fingerprint_and_copy(self):
        class FakeSale:
            sale_number = 'SALE-9'
            total = '100.00'
            pk = 9

        title, content = build_manager_sale_queue_notice(
            author=self.sales,
            source=SOURCE_SALE_COMPLETE,
            record_id=9,
            sale=FakeSale(),
        )
        self.assertEqual(title, 'Clear and move: SALE-9')
        self.assertIn('Ann Cash added sale SALE-9 (KES 100.00)', content)
        self.assertIn('To do', content)
        self.assertIn('Past', content)
        self.assertIn(sale_queue_notice_fingerprint(SOURCE_SALE_COMPLETE, 9), content)
        back_title, back_content = build_manager_sale_queue_notice(
            author=self.sales,
            source=SOURCE_SALE_BACKFILL,
            record_id=12,
            entity_repr='Past sale 2026-09-20',
        )
        self.assertIn('Clear and move: Past sale 2026-09-20', back_title)
        self.assertIn('Ann Cash added Past sale 2026-09-20', back_content)
        self.assertIn(sale_queue_notice_fingerprint(SOURCE_SALE_BACKFILL, 12), back_content)

    def test_queue_puts_todo_on_manager_board_not_salesperson(self):
        class FakeSale:
            sale_number = 'SALE-11'
            total = '50.00'
            pk = 11

        notes = notify_managers_sale_queued(
            author=self.sales,
            source=SOURCE_SALE_COMPLETE,
            record_id=11,
            sale=FakeSale(),
        )
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertEqual(note.assigned_to_id, self.manager.id)
        self.assertEqual(note.author_id, self.manager.id)
        self.assertEqual(note.board_column, 'todo')
        self.assertFalse(note.is_done)
        self.assertFalse(note.in_progress)
        self.assertTrue(note.title.startswith('Clear and move'))
        self.assertFalse(
            DailyNote.objects.filter(assigned_to=self.sales, content__contains='ref: sale_complete/11').exists()
        )
        again = notify_managers_sale_queued(
            author=self.sales,
            source=SOURCE_SALE_COMPLETE,
            record_id=11,
            sale=FakeSale(),
        )
        self.assertEqual([n.pk for n in again], [note.pk])
        self.assertEqual(
            DailyNote.objects.filter(content__contains='ref: sale_complete/11').count(),
            1,
        )

    def test_approve_moves_card_to_past_and_resubmit_reopens_todo(self):
        notes = notify_managers_sale_queued(
            author=self.sales,
            source=SOURCE_SALE_BACKFILL,
            record_id=44,
            entity_repr='Past sale 2026-09-01',
        )
        self.assertEqual(notes[0].board_column, 'todo')
        moved = complete_manager_queue_notes(source=SOURCE_SALE_BACKFILL, record_id=44)
        self.assertEqual(moved, 1)
        notes[0].refresh_from_db()
        self.assertEqual(notes[0].board_column, 'past')
        self.assertTrue(notes[0].is_done)
        self.assertEqual(complete_manager_queue_notes(source=SOURCE_SALE_BACKFILL, record_id=44), 0)

        class Change:
            action_type = 'sale_backfill'
            id = 44
            entity_id = 'new'
            entity_repr = 'Past sale 2026-09-01'

        self.assertEqual(complete_manager_notes_for_change(Change()), 0)
        reopened = notify_managers_sale_queued(
            author=self.sales,
            source=SOURCE_SALE_BACKFILL,
            record_id=44,
            entity_repr='Past sale 2026-09-01',
        )
        self.assertEqual(reopened[0].pk, notes[0].pk)
        reopened[0].refresh_from_db()
        self.assertEqual(reopened[0].board_column, 'todo')
        self.assertFalse(reopened[0].is_done)

    def test_skips_author_and_missing_inputs(self):
        self.assertEqual(
            manager_notice_recipients(exclude_user=self.manager),
            [],
        )
        self.assertEqual(
            notify_managers_sale_queued(author=None, source=SOURCE_SALE_COMPLETE, record_id=1),
            [],
        )
        self.assertEqual(
            notify_managers_sale_queued(author=self.sales, source=SOURCE_SALE_COMPLETE, record_id=None),
            [],
        )
        self.assertEqual(complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=None), 0)
        self.assertEqual(complete_sale_return_notes(record_id=None), 0)
        self.assertEqual(complete_manager_notes_for_change(type('C', (), {'action_type': 'expense', 'id': 1})()), 0)
        self.assertEqual(
            notify_managers_for_change(author=self.sales, change=type('C', (), {'action_type': 'expense'})()),
            [],
        )
        class SaleChange:
            action_type = 'sale_complete'
            entity_id = 55
            entity_repr = 'S-55'
            id = 55

        queued = notify_managers_for_change(author=self.sales, change=SaleChange())
        self.assertEqual(len(queued), 1)
        self.assertEqual(
            complete_manager_notes_for_change(SaleChange()),
            1,
        )
        class BackfillChange:
            action_type = 'sale_backfill'
            id = 66
            entity_repr = 'Past sale'

        backfill = notify_managers_for_change(author=self.sales, change=BackfillChange())
        self.assertEqual(len(backfill), 1)

    def test_queue_writer_swallows_errors(self):
        from unittest.mock import patch

        with patch(
            'daily_notes.services.create_notes_for_assignees',
            side_effect=RuntimeError('db'),
        ):
            self.assertEqual(
                notify_managers_sale_queued(
                    author=self.sales,
                    source=SOURCE_SALE_COMPLETE,
                    record_id=99,
                ),
                [],
            )

    def test_complete_note_writers_swallow_save_errors(self):
        from unittest.mock import patch

        DailyNote.objects.create(
            note_date=date.today(),
            title='Return',
            content='x\nref: reject/sale/7/',
            author=self.sales,
            assigned_to=self.sales,
            is_sticky=True,
        )
        DailyTask.objects.create(
            task_date=date.today(),
            title='Return',
            description='x\nref: reject/sale/7/',
            author=self.manager,
            assigned_to=self.sales,
        )
        with patch.object(DailyNote, 'move_to_board', side_effect=RuntimeError('db')):
            self.assertEqual(complete_sale_return_notes(record_id=7), 0)
        with patch.object(DailyTask, 'mark_done', side_effect=RuntimeError('db')):
            self.assertEqual(complete_sale_return_notes(record_id=7), 1)

        notes = notify_managers_sale_queued(
            author=self.sales,
            source=SOURCE_SALE_COMPLETE,
            record_id=8,
            entity_repr='S-8',
        )
        notes[0].move_to_board('past')
        notes[0].save()
        with patch.object(DailyNote, 'move_to_board', side_effect=RuntimeError('db')):
            reopened = notify_managers_sale_queued(
                author=self.sales,
                source=SOURCE_SALE_COMPLETE,
                record_id=8,
                entity_repr='S-8',
            )
            self.assertEqual(reopened, [])
        notes[0].refresh_from_db()
        notes[0].move_to_board('todo')
        notes[0].save()
        with patch.object(DailyNote, 'move_to_board', side_effect=RuntimeError('db')):
            self.assertEqual(
                complete_manager_queue_notes(source=SOURCE_SALE_COMPLETE, record_id=8),
                0,
            )

    def test_recipients_fall_back_to_sales_approvers(self):
        from accounts.models import Permission, Role, UserProfile
        from accounts.role_definitions import ROLE_MANAGER

        Role.objects.filter(name=ROLE_MANAGER).update(name='_renamed_manager')
        UserProfile.objects.filter(user=self.manager).update(role='cashier', custom_role=None)
        perm = Permission.objects.get_or_create(module='sales', action='approve')[0]
        role = Role.objects.create(name='Sale checker')
        role.permissions.add(perm)
        checker = User.objects.create_user('sale_checker', password='x')
        UserProfile.objects.create(
            user=checker,
            role='cashier',
            custom_role=role,
            is_active=True,
        )
        recips = manager_notice_recipients(exclude_user=self.sales)
        self.assertEqual([u.pk for u in recips], [checker.pk])
