"""Ask a colleague to review a finished note, then read that review back."""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from daily_notes.models import DailyNote, DailyNoteReview
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase

OTHER_PHONE = '0711777001'


class DailyNoteReviewTests(ManagerAPITestCase):
    """Review tags on the notes board: who can ask, who can answer, what repeats do."""

    def setUp(self):
        super().setUp()
        ensure_permissions()
        roles = sync_default_roles(created_by=self.manager_user)
        self.reviewer = User.objects.create_user('note_reviewer', password='x', first_name='Rita')
        UserProfile.objects.create(
            user=self.reviewer,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        self.outsider = User.objects.create_user('note_outsider', password='x')
        UserProfile.objects.create(
            user=self.outsider,
            role='cashier',
            custom_role=roles[ROLE_SALES],
            is_active=True,
        )
        self.note = DailyNote.objects.create(
            note_date=timezone.localdate(),
            title='Close the till',
            content='Counted and locked.',
            author=self.manager_user,
            assigned_to=self.manager_user,
            is_done=True,
        )

    def test_finished_note_can_be_tagged_and_reviewed(self):
        asked = self.client.post(
            f'/api/daily-notes/notes/{self.note.id}/request-review/',
            {'user_ids': [self.reviewer.id]},
            format='json',
        )
        self.assertEqual(asked.status_code, status.HTTP_200_OK, asked.data)
        self.assertEqual(asked.data['reviews'][0]['reviewer_name'], 'Rita')
        self.assertEqual(asked.data['reviews'][0]['status'], 'pending')
        self.assertNotIn(OTHER_PHONE, str(asked.data))

        reviewer = APIClient()
        reviewer.force_authenticate(user=self.reviewer)
        listed = reviewer.get(
            '/api/daily-notes/notes/',
            {'note_date': timezone.localdate().isoformat()},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        rows = listed.data.get('results', listed.data)
        self.assertTrue(any(row['id'] == self.note.id for row in rows))

        review_id = asked.data['reviews'][0]['id']
        done = reviewer.post(
            f'/api/daily-notes/notes/{self.note.id}/reviews/{review_id}/complete/',
            {'comment': 'Looks correct'},
            format='json',
        )
        self.assertEqual(done.status_code, status.HTTP_200_OK, done.data)
        self.assertEqual(done.data['reviews'][0]['status'], 'reviewed')
        self.assertEqual(done.data['reviews'][0]['comment'], 'Looks correct')
        self.assertNotIn(OTHER_PHONE, str(done.data))

    def test_open_note_self_tag_and_stranger_are_refused(self):
        open_note = DailyNote.objects.create(
            note_date=timezone.localdate(),
            title='Still open',
            content='Not finished.',
            author=self.manager_user,
        )
        refused = self.client.post(
            f'/api/daily-notes/notes/{open_note.id}/request-review/',
            {'user_ids': [self.reviewer.id]},
            format='json',
        )
        self.assertEqual(refused.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn(OTHER_PHONE, str(refused.data))

        self_tag = self.client.post(
            f'/api/daily-notes/notes/{self.note.id}/request-review/',
            {'user_ids': [self.manager_user.id]},
            format='json',
        )
        self.assertEqual(self_tag.status_code, status.HTTP_400_BAD_REQUEST)

        anon = APIClient()
        anon_res = anon.post(
            f'/api/daily-notes/notes/{self.note.id}/request-review/',
            {'user_ids': [self.reviewer.id]},
            format='json',
        )
        self.assertEqual(anon_res.status_code, status.HTTP_401_UNAUTHORIZED)

        outsider = APIClient()
        outsider.force_authenticate(user=self.outsider)
        hidden = outsider.post(
            f'/api/daily-notes/notes/{self.note.id}/request-review/',
            {'user_ids': [self.reviewer.id]},
            format='json',
        )
        self.assertIn(hidden.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.assertNotIn(OTHER_PHONE, str(hidden.data))
        self.assertEqual(DailyNoteReview.objects.filter(daily_note=self.note).count(), 0)

    def test_feature_off_does_not_create_a_review(self):
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='daily_notes',
            defaults={'is_enabled': True},
        )
        was_enabled = module.is_enabled
        module.is_enabled = True
        module.save(update_fields=['is_enabled'])
        feature, _ = ModuleFeature.objects.get_or_create(
            module=module,
            feature_key='note_review',
            defaults={'feature_name': 'Ask someone to review', 'is_enabled': False},
        )
        feature.is_enabled = False
        feature.save(update_fields=['is_enabled'])
        try:
            res = self.client.post(
                f'/api/daily-notes/notes/{self.note.id}/request-review/',
                {'user_ids': [self.reviewer.id]},
                format='json',
            )
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(DailyNoteReview.objects.filter(daily_note=self.note).count(), 0)
        finally:
            feature.is_enabled = True
            feature.save(update_fields=['is_enabled'])
            module.is_enabled = was_enabled
            module.save(update_fields=['is_enabled'])

    def test_asking_the_same_person_eight_times_stays_one_row(self):
        for _ in range(8):
            res = self.client.post(
                f'/api/daily-notes/notes/{self.note.id}/request-review/',
                {'user_ids': [self.reviewer.id]},
                format='json',
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(
            DailyNoteReview.objects.filter(daily_note=self.note, reviewer=self.reviewer).count(),
            1,
        )

    def test_reviewer_list_has_names_and_not_the_other_phone(self):
        res = self.client.get('/api/daily-notes/notes/reviewers/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        ids = [row['id'] for row in res.data]
        self.assertIn(self.reviewer.id, ids)
        self.assertNotIn(self.manager_user.id, ids)
        self.assertNotIn(OTHER_PHONE, str(res.data))
