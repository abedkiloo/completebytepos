"""Fill remaining daily_notes gate coverage gaps."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.test import RequestFactory
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, sync_default_roles
from daily_notes.models import (
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    DailyNote,
    DailyNoteChecklistItem,
    DailyNoteReview,
    DailyTask,
)
from daily_notes.serializers import (
    DailyNoteSerializer,
    DailyTaskSerializer,
    _parse_multipart_payload,
    attach_note_images,
    replace_note_checklist,
)
from daily_notes.services import (
    DailyNoteService,
    DailyTaskService,
    carried_over_days,
    create_notes_for_assignees,
    parse_filter_date,
)
from daily_notes.tests.test_priority_and_features import _set_feature
from daily_notes.tests.test_views import _seed_daily_notes_module
from daily_notes.view_mixins import DailyAuthorScopedViewSetMixin
from daily_notes.views import DailyNoteViewSet, DailyTaskViewSet
from settings.models import ModuleSetting, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


class DailyNotesServiceGapTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.today = date.today()

    def test_parse_filter_date_invalid_and_carried_over_bad_origin(self):
        self.assertIsNone(parse_filter_date('not-a-date'))
        self.assertIsNone(parse_filter_date('2025-13-40'))
        self.assertEqual(
            carried_over_days(origin='garbage', as_of=self.today),
            0,
        )
        self.assertEqual(parse_filter_date(self.today), self.today)

    def test_create_notes_truncates_huge_staff_fanout(self):
        fake_users = [User(id=i, username=f'u{i}') for i in range(1, 505)]
        with patch('daily_notes.services.active_staff_users', return_value=fake_users):
            with patch.object(DailyNote.objects, 'bulk_create', side_effect=lambda rows, **kw: rows):
                notes = create_notes_for_assignees(
                    author=self.manager_user,
                    note_date=self.today,
                    content='Broadcast',
                    assign_to_all=True,
                )
        self.assertEqual(len(notes), 500)

    def test_task_person_filter_and_invalid_day_raw(self):
        from django.core.exceptions import ValidationError

        alice = User.objects.create_user('gap_alice', password='x')
        DailyTask.objects.create(
            task_date=self.today,
            title='Alice task',
            author=self.manager_user,
            assigned_to=alice,
        )
        DailyTask.objects.create(
            task_date=self.today,
            title='Other task',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        # Invalid day_raw hits the else branch then Django date prep raises.
        with self.assertRaises(ValidationError):
            DailyTaskService().build_queryset(
                user=self.manager_user,
                view_all=True,
                filters={'person': alice.id, 'task_date': 'not-iso'},
            )
        person_only = DailyTaskService().build_queryset(
            user=self.manager_user,
            view_all=True,
            filters={'person': alice.id},
        )
        self.assertEqual(person_only.count(), 1)
        self.assertEqual(person_only.first().assigned_to_id, alice.id)

    def test_pending_count_for_user(self):
        DailyTask.objects.create(
            task_date=self.today,
            title='Open',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        DailyTask.objects.create(
            task_date=self.today,
            title='Done',
            is_done=True,
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        self.assertEqual(
            DailyTaskService().pending_count_for_user(user=self.manager_user),
            1,
        )


class DailyNotesSerializerGapTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()

    def test_replace_checklist_accepts_model_instances_and_skips_blank(self):
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Has checklist',
            author=self.manager_user,
        )
        existing = DailyNoteChecklistItem(
            label='From model',
            is_done=True,
            sort_order=None,
        )
        replace_note_checklist(note, [existing, {'label': '  ', 'is_done': False}])
        labels = list(note.checklist_items.values_list('label', flat=True))
        self.assertEqual(labels, ['From model'])
        self.assertTrue(note.checklist_items.get().is_done)
        self.assertEqual(str(note.checklist_items.get()), 'From model (done)')
        open_item = DailyNoteChecklistItem.objects.create(
            daily_note=note, label='Still open', sort_order=1
        )
        self.assertEqual(str(open_item), 'Still open (open)')

    def test_create_note_with_board_column_and_done_requires_content(self):
        today = timezone.localdate().isoformat()
        created = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': today,
                'content': 'Board create',
                'board_column': 'doing',
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data['board_column'], 'doing')

        bad = self.client.post(
            '/api/daily-notes/notes/',
            {'note_date': today, 'content': '', 'is_done': True},
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_task_serializer_unassigned_name_and_done_requires_title(self):
        task = DailyTask(
            task_date=date.today(),
            title='Solo',
            author=self.manager_user,
            assigned_to=None,
        )
        data = DailyTaskSerializer(
            task,
            context={'request': type('R', (), {'user': self.manager_user})()},
        ).data
        self.assertEqual(data['assigned_to_name'], '')

        existing = DailyTask.objects.create(
            task_date=date.today(),
            title='Has title',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        existing.title = ''
        existing.save(update_fields=['title'])
        ser = DailyTaskSerializer(
            existing,
            data={'is_done': True},
            partial=True,
            context={'request': type('R', (), {'user': self.manager_user})()},
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('title', ser.errors)


class DailyNotesViewGapTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.sales_user = User.objects.create_user('gap_sales', password='sales123')
        UserProfile.objects.create(
            user=self.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def test_staff_search_and_assigned_to_filter_param(self):
        staff = self.client.get('/api/daily-notes/notes/staff/', {'q': 'phase2'})
        self.assertEqual(staff.status_code, status.HTTP_200_OK)
        self.assertTrue(any(row['username'] == 'phase2_manager' for row in staff.data))

        DailyNote.objects.create(
            note_date=date.today(),
            content='Assigned filter',
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        filtered = self.client.get(
            '/api/daily-notes/notes/',
            {'assigned_to': self.sales_user.id, 'note_date': str(date.today())},
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        rows = filtered.data.get('results') or filtered.data
        self.assertTrue(any(r['content'] == 'Assigned filter' for r in rows))

    def test_checklist_toggle_forbidden_for_outsider(self):
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Private',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        item = DailyNoteChecklistItem.objects.create(
            daily_note=note, label='Nope', sort_order=0
        )
        token = RefreshToken.for_user(self.sales_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        # Ensure sales can access module but not this note.
        ModuleSetting.objects.update_or_create(
            module='daily_notes',
            key='allow_sales_view_all',
            defaults={
                'label': 'allow_sales_view_all',
                'description': '',
                'default_value': False,
                'value': False,
            },
        )
        cache.clear()
        res = self.client.post(
            f'/api/daily-notes/notes/{note.id}/checklist-items/{item.id}/toggle-done/'
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_may_toggle_note(self):
        admin = User.objects.create_superuser('gap_admin', 'a@b.co', 'x')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Admin tick',
            author=self.manager_user,
            assigned_to=self.sales_user,
        )
        view = DailyNoteViewSet()
        view.request = type('R', (), {'user': admin})()
        self.assertTrue(view._may_toggle_note(note))

    def test_task_edit_toggle_permissions_and_pending_count(self):
        other = User.objects.create_user('gap_other', password='x')
        UserProfile.objects.create(
            user=other,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        task = DailyTask.objects.create(
            task_date=date.today(),
            title='Owned by manager',
            author=self.manager_user,
            assigned_to=other,
        )
        # Assignee can see the task but cannot edit/delete (not author / view_all).
        token = RefreshToken.for_user(other)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        ModuleSetting.objects.update_or_create(
            module='daily_notes',
            key='allow_sales_view_all',
            defaults={
                'label': 'allow_sales_view_all',
                'description': '',
                'default_value': False,
                'value': False,
            },
        )
        cache.clear()
        patch = self.client.patch(
            f'/api/daily-notes/tasks/{task.id}/',
            {'title': 'Hacked'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)
        delete = self.client.delete(f'/api/daily-notes/tasks/{task.id}/')
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

        # Assignee may toggle; author may toggle; superuser may edit.
        view = DailyTaskViewSet()
        view.request = type('R', (), {'user': other})()
        self.assertTrue(view._may_toggle_task(task))
        view.request = type('R', (), {'user': self.manager_user})()
        self.assertTrue(view._may_toggle_task(task))
        admin = User.objects.create_superuser('gap_su', 's@b.co', 'x')
        view.request = type('R', (), {'user': admin})()
        self.assertTrue(view._may_edit_task(task))
        self.assertTrue(view._may_toggle_task(task))

        # Manager pending-count happy path
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.manager_user).access_token}'
        )
        count = self.client.get('/api/daily-notes/tasks/pending-count/')
        self.assertEqual(count.status_code, status.HTTP_200_OK)
        self.assertIn('count', count.data)

    def test_pending_count_denied_without_access(self):
        ModuleSettings.objects.update_or_create(
            module_name='daily_notes',
            defaults={'is_enabled': True},
        )
        empty_role = Role.objects.create(name='No desk gap', is_active=True)
        orphan = User.objects.create_user('gap_orphan', password='x')
        UserProfile.objects.create(user=orphan, role='cashier', custom_role=empty_role)
        view = DailyTaskViewSet()
        view.request = type('R', (), {'user': orphan})()
        view.format_kwarg = None
        denied = view.pending_count(view.request)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)


class DailyNotesHundredPercentGapTests(ManagerAPITestCase):
    """Hit remaining miss lines on gated daily_notes modules."""

    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()
        self.factory = RequestFactory()
        self.today = date.today()
        self.sales_user = User.objects.create_user(
            'gap100_sales', password='sales123', first_name='Gap'
        )
        UserProfile.objects.create(
            user=self.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def test_review_str_and_mixin_update_forbidden(self):
        note = DailyNote.objects.create(
            note_date=self.today,
            content='Reviewable',
            author=self.manager_user,
            assigned_to=self.manager_user,
            is_done=True,
        )
        review = DailyNoteReview.objects.create(
            daily_note=note,
            reviewer=self.sales_user,
            requested_by=self.manager_user,
        )
        self.assertIn(str(note.id), str(review))
        self.assertIn(str(self.sales_user.id), str(review))

        other_note = DailyNote.objects.create(
            note_date=self.today,
            content='Owned by sales',
            author=self.sales_user,
        )
        view = DailyNoteViewSet()
        request = self.factory.patch(f'/api/daily-notes/notes/{other_note.id}/')
        request.user = self.manager_user
        view.request = request
        view.kwargs = {'pk': other_note.id}
        view.format_kwarg = None
        view.get_object = lambda: other_note
        view._author_may_modify = lambda instance: False
        denied = DailyAuthorScopedViewSetMixin.update(view, request)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        view._author_may_modify = lambda instance: True
        with patch(
            'rest_framework.mixins.UpdateModelMixin.update',
            return_value=Response({'ok': True}),
        ):
            allowed = DailyAuthorScopedViewSetMixin.update(view, request)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_board_column_only_and_blocking_schema_error(self):
        view = DailyNoteViewSet()
        self.assertFalse(view._board_column_only_move('todo'))
        self.assertFalse(view._board_column_only_move(None))

        request = self.factory.get('/api/daily-notes/notes/blocking/')
        request.user = self.manager_user
        view.request = request
        view.format_kwarg = None
        view.get_serializer = lambda *a, **k: MagicMock(data=[])
        with patch.object(
            DailyNoteService,
            'blocking_for_user',
            side_effect=Exception('column daily_notes_dailynote.image does not exist'),
        ):
            view.entry_service = DailyNoteService()
            res = view.blocking(request)
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        with patch.object(
            DailyNoteService,
            'blocking_for_user',
            side_effect=RuntimeError('something else'),
        ):
            view.entry_service = DailyNoteService()
            with self.assertRaises(RuntimeError):
                view.blocking(request)

    def test_reviewers_access_feature_and_search(self):
        view = DailyNoteViewSet()
        orphan = User.objects.create_user('gap100_orphan', password='x')
        empty_role = Role.objects.create(name='Gap100 empty', is_active=True)
        UserProfile.objects.create(user=orphan, role='cashier', custom_role=empty_role)
        request = self.factory.get('/api/daily-notes/notes/reviewers/')
        request.user = orphan
        view.request = request
        view.format_kwarg = None
        denied = view.reviewers(request)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        _set_feature('daily_notes', 'note_review', False)
        request = self.factory.get('/api/daily-notes/notes/reviewers/')
        request.user = self.manager_user
        view.request = request
        off = view.reviewers(request)
        self.assertEqual(off.status_code, status.HTTP_403_FORBIDDEN)
        _set_feature('daily_notes', 'note_review', True)

        searched = self.client.get(
            '/api/daily-notes/notes/reviewers/',
            {'q': 'Gap'},
        )
        self.assertEqual(searched.status_code, status.HTTP_200_OK)
        self.assertTrue(any(r['id'] == self.sales_user.id for r in searched.data))

    def test_request_and_complete_review_edge_branches(self):
        note = DailyNote.objects.create(
            note_date=self.today,
            content='Done note',
            author=self.manager_user,
            assigned_to=self.manager_user,
            is_done=True,
        )
        view = DailyNoteViewSet()
        view.format_kwarg = None
        view.get_object = lambda: note
        view.get_queryset = lambda: DailyNote.objects.filter(pk=note.pk)
        view.get_serializer = lambda *a, **k: MagicMock(
            data={'id': note.id, 'reviews': []}
        )

        stranger = User.objects.create_user('gap100_stranger', password='x')
        UserProfile.objects.create(
            user=stranger,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        request = self.factory.post(
            f'/api/daily-notes/notes/{note.id}/request-review/',
            data={'user_ids': [self.sales_user.id]},
            content_type='application/json',
        )
        request.user = stranger
        request.data = {'user_ids': [self.sales_user.id]}
        view.request = request
        forbidden = view.request_review(request, pk=note.id)
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        _set_feature('daily_notes', 'note_review', False)
        request.user = self.manager_user
        view.request = request
        complete_off = view.complete_review(request, pk=note.id, review_id=999)
        self.assertEqual(complete_off.status_code, status.HTTP_403_FORBIDDEN)
        _set_feature('daily_notes', 'note_review', True)

        missing = view.complete_review(request, pk=note.id, review_id=999999)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

        review = DailyNoteReview.objects.create(
            daily_note=note,
            reviewer=self.sales_user,
            requested_by=self.manager_user,
        )
        wrong_user = view.complete_review(request, pk=note.id, review_id=review.id)
        self.assertEqual(wrong_user.status_code, status.HTTP_403_FORBIDDEN)

        request.user = self.sales_user
        view.request = request
        request.data = {'comment': 'x' * 501}
        too_long = view.complete_review(request, pk=note.id, review_id=review.id)
        self.assertEqual(too_long.status_code, status.HTTP_400_BAD_REQUEST)

    def test_services_stale_cleanup_exception_and_priority_filter(self):
        with patch(
            'daily_notes.approval_notice.complete_stale_approval_notices',
            side_effect=RuntimeError('schema lag'),
        ):
            rows = DailyNoteService().blocking_for_user(user=self.manager_user)
        self.assertEqual(list(rows), [])

        DailyTask.objects.create(
            task_date=self.today,
            title='High one',
            priority=PRIORITY_HIGH,
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        DailyTask.objects.create(
            task_date=self.today,
            title='Med one',
            priority=PRIORITY_MEDIUM,
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        high_only = DailyTaskService().build_queryset(
            user=self.manager_user,
            view_all=True,
            filters={'priority': 'high', 'task_date': str(self.today)},
        )
        self.assertEqual(high_only.count(), 1)
        self.assertEqual(high_only.first().title, 'High one')

    def test_multipart_payload_and_image_helpers(self):
        qd = QueryDict(mutable=True)
        qd.update({'content': 'Hello', 'assigned_to': '', 'assigned_role': ''})
        qd.setlist('checklist_items', ['  '])
        parsed = _parse_multipart_payload(qd)
        self.assertEqual(parsed['checklist_items'], [])
        self.assertIsNone(parsed['assigned_to'])
        self.assertIsNone(parsed['assigned_role'])
        qd_json = QueryDict(mutable=True)
        qd_json.setlist('checklist_items', ['[]'])
        self.assertEqual(_parse_multipart_payload(qd_json)['checklist_items'], [])

        qd2 = QueryDict(mutable=True)
        qd2.setlist('checklist_items', ['{not-json'])
        with self.assertRaises(Exception):
            _parse_multipart_payload(qd2)

        qd3 = QueryDict(mutable=True)
        qd3.setlist('tag', ['a', 'b'])
        qd3['content'] = 'x'
        multi = _parse_multipart_payload(qd3)
        self.assertEqual(multi['tag'], ['a', 'b'])

        blank = _parse_multipart_payload({'checklist_items': '  '})
        self.assertEqual(blank['checklist_items'], [])
        with self.assertRaises(Exception):
            _parse_multipart_payload({'checklist_items': '{bad'})
        ok = _parse_multipart_payload({'checklist_items': '[{"label":"A"}]'})
        self.assertEqual(ok['checklist_items'][0]['label'], 'A')

        note = DailyNote.objects.create(
            note_date=self.today,
            content='Img',
            author=self.manager_user,
        )
        with patch(
            'utils.image_upload.prepare_uploaded_image',
            return_value=None,
        ):
            attach_note_images([note], uploaded_file=MagicMock())

        ser = DailyNoteSerializer(
            note,
            context={'request': self.factory.get('/')},
        )
        broken = MagicMock()
        type(broken).url = PropertyMock(side_effect=ValueError('missing'))
        note.image = broken
        self.assertIsNone(ser.get_image_url(note))

    def test_serializer_update_feature_gates_and_done_content(self):
        note = DailyNote.objects.create(
            note_date=self.today,
            content='',
            author=self.manager_user,
            assigned_to=self.manager_user,
        )
        ser = DailyNoteSerializer(
            note,
            data={'is_done': True},
            partial=True,
            context={'request': SimpleNamespace(user=self.manager_user)},
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('content', ser.errors)

        filled = DailyNote.objects.create(
            note_date=self.today,
            content='Keep',
            author=self.manager_user,
            assigned_to=self.manager_user,
            priority=PRIORITY_HIGH,
            is_sticky=True,
        )
        _set_feature('daily_notes', 'note_priority', False)
        _set_feature('daily_notes', 'sticky_notes', False)
        _set_feature('daily_notes', 'checklists', False)
        try:
            upd = DailyNoteSerializer(
                filled,
                data={
                    'priority': PRIORITY_HIGH,
                    'is_sticky': True,
                    'checklist_items': [{'label': 'Skip', 'is_done': False}],
                },
                partial=True,
                context={'request': SimpleNamespace(user=self.manager_user)},
            )
            self.assertTrue(upd.is_valid(), upd.errors)
            saved = upd.save()
            self.assertEqual(saved.priority, PRIORITY_MEDIUM)
            self.assertFalse(saved.is_sticky)
            self.assertEqual(saved.checklist_items.count(), 0)
        finally:
            _set_feature('daily_notes', 'note_priority', True)
            _set_feature('daily_notes', 'sticky_notes', True)
            _set_feature('daily_notes', 'checklists', True)

        _set_feature('daily_notes', 'note_priority', False)
        try:
            task_ser = DailyTaskSerializer(
                data={
                    'task_date': str(self.today),
                    'title': 'No prio feat',
                    'priority': PRIORITY_HIGH,
                },
                context={'request': SimpleNamespace(user=self.manager_user)},
            )
            self.assertTrue(task_ser.is_valid(), task_ser.errors)
            task = task_ser.save(author=self.manager_user)
            self.assertEqual(task.priority, PRIORITY_MEDIUM)
        finally:
            _set_feature('daily_notes', 'note_priority', True)


class ApprovalNoticeAndReviewGapTests(ManagerAPITestCase):
    """Close approval_notice + note_reviews miss lines."""

    def setUp(self):
        super().setUp()
        sync_default_roles()
        _seed_daily_notes_module()

    def test_sale_label_phone_and_summary_exceptions(self):
        from daily_notes.approval_notice import (
            _sale_correction_summary,
            _sale_customer_label,
            complete_sale_approved_notices,
            notify_managers_sale_queued,
        )

        customer = SimpleNamespace(name='', phone='0711000111')
        sale = SimpleNamespace(
            customer_name='',
            customer=customer,
            customer_phone='',
            items=None,
            total=10,
            amount_paid=10,
            payment_method='mpesa',
            pk=1,
        )
        self.assertIn('0711000111', _sale_customer_label(sale))

        sale2 = SimpleNamespace(
            customer_name='Ada',
            customer=None,
            customer_phone='0722000222',
            items=None,
            total=1,
            amount_paid=1,
            payment_method='cash',
            pk=2,
        )
        self.assertIn('0722000222', _sale_customer_label(sale2))

        broken_items = SimpleNamespace(
            all=MagicMock(side_effect=RuntimeError('db')),
        )
        sale3 = SimpleNamespace(
            customer_name='Bo',
            customer=None,
            customer_phone='',
            items=broken_items,
            total=5,
            amount_paid=5,
            payment_method='cash',
            pk=3,
        )
        summary = _sale_correction_summary(sale3)
        self.assertIn('0 item', summary)

        self.assertEqual(complete_sale_approved_notices(sale=None), 0)

        with patch(
            'daily_notes.approval_notice.manager_notice_recipients',
            return_value=[],
        ):
            self.assertEqual(
                notify_managers_sale_queued(
                    author=self.manager_user,
                    source='sale_complete',
                    record_id=99,
                ),
                [],
            )

    def test_note_reviews_validation_branches(self):
        from daily_notes.note_reviews import (
            _display,
            complete_note_review,
            request_note_reviews,
        )

        self.assertEqual(_display(None), '')
        note = DailyNote.objects.create(
            note_date=date.today(),
            content='Done',
            author=self.manager_user,
            assigned_to=self.manager_user,
            is_done=True,
        )
        with self.assertRaises(ValidationError):
            request_note_reviews(
                note=note, reviewer_ids=[1], requested_by=None
            )
        with self.assertRaises(ValidationError):
            request_note_reviews(
                note=note, reviewer_ids=['abc'], requested_by=self.manager_user
            )
        with self.assertRaises(ValidationError):
            request_note_reviews(
                note=note, reviewer_ids=[0], requested_by=self.manager_user
            )
        with self.assertRaises(ValidationError):
            request_note_reviews(
                note=note, reviewer_ids=[], requested_by=self.manager_user
            )
        with self.assertRaises(ValidationError):
            request_note_reviews(
                note=note,
                reviewer_ids=[1, 2, 3, 4, 5, 6],
                requested_by=self.manager_user,
            )
        with self.assertRaises(ValidationError):
            request_note_reviews(
                note=note,
                reviewer_ids=[self.manager_user.id],
                requested_by=self.manager_user,
            )
        with self.assertRaises(ValidationError):
            request_note_reviews(
                note=note,
                reviewer_ids=[999999],
                requested_by=self.manager_user,
            )

        reviewers = []
        for i in range(5):
            u = User.objects.create_user(f'gap_rev_{i}', password='x')
            UserProfile.objects.create(
                user=u,
                role='cashier',
                custom_role=Role.objects.get(name=ROLE_SALES),
                is_active=True,
            )
            reviewers.append(u)
        request_note_reviews(
            note=note,
            reviewer_ids=[u.id for u in reviewers],
            requested_by=self.manager_user,
        )
        extra = User.objects.create_user('gap_rev_extra', password='x')
        UserProfile.objects.create(
            user=extra,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            request_note_reviews(
                note=note,
                reviewer_ids=[extra.id],
                requested_by=self.manager_user,
            )

        row = note.reviews.first()
        complete_note_review(review=row, comment='ok')
        with self.assertRaises(ValidationError):
            complete_note_review(review=row, comment='again')

        row2 = note.reviews.exclude(pk=row.pk).first()
        with self.assertRaises(ValidationError):
            complete_note_review(review=row2, comment='x' * 501)

        # Re-request a finished reviewer resets to pending (lines 97-101).
        request_note_reviews(
            note=note,
            reviewer_ids=[row.reviewer_id],
            requested_by=self.manager_user,
        )
        row.refresh_from_db()
        self.assertEqual(row.status, DailyNoteReview.STATUS_PENDING)
