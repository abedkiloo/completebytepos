"""Reject returns the request to the maker and writes a Daily notes notice."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from approvals.models import PendingChange
from daily_notes.models import DailyNote, DailyTask
from products.models import Category, Product
from settings.models import StoreSettings
from utils.tests.api_test_base import ManagerAPITestCase


class RejectReturnsToRequesterTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.checker = User.objects.create_user(
            'return_checker', password='chk123', is_staff=True
        )
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.category = Category.objects.create(name='Return Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Return Product',
            sku='RET-1',
            category=cls.category,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled'])
        PendingChange.objects.all().delete()
        DailyNote.objects.all().delete()
        DailyTask.objects.all().delete()

    def _checker_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def _queue_price_change(self):
        resp = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '180.00', 'reason': 'Seasonal price'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        return PendingChange.objects.get()

    def test_reject_writes_daily_note_and_task_for_maker(self):
        pending = self._queue_price_change()
        checker = self._checker_client()
        resp = checker.post(
            f'/api/approvals/pending-changes/{pending.id}/reject/',
            {'rejection_reason': 'Price is too high for this pack size'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        pending.refresh_from_db()
        self.assertEqual(pending.status, PendingChange.STATUS_REJECTED)
        note = DailyNote.objects.get(author=self.manager_user)
        self.assertIn('Approval rejected', note.title)
        self.assertIn('Price is too high', note.content)
        self.assertIn(f'id: {pending.id}', note.content)
        task = DailyTask.objects.get(assigned_to=self.manager_user)
        self.assertFalse(task.is_done)
        self.assertEqual(task.author_id, self.checker.id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('100'))

    def test_maker_can_resubmit_rejected_change(self):
        pending = self._queue_price_change()
        checker = self._checker_client()
        checker.post(
            f'/api/approvals/pending-changes/{pending.id}/reject/',
            {'rejection_reason': 'Need a supplier quote'},
            format='json',
        )
        resubmit = self.client.post(
            f'/api/approvals/pending-changes/{pending.id}/resubmit/',
            {'reason': 'Quote attached verbally'},
            format='json',
        )
        self.assertEqual(resubmit.status_code, status.HTTP_200_OK, resubmit.data)
        pending.refresh_from_db()
        self.assertEqual(pending.status, PendingChange.STATUS_PENDING)
        self.assertEqual(pending.rejection_reason, '')
        self.assertIsNone(pending.checked_by_id)
        self.assertIn('[Resubmitted] Quote attached verbally', pending.reason)

    def test_other_user_cannot_resubmit(self):
        pending = self._queue_price_change()
        checker = self._checker_client()
        checker.post(
            f'/api/approvals/pending-changes/{pending.id}/reject/',
            {'rejection_reason': 'No'},
            format='json',
        )
        other = User.objects.create_user('other_maker', password='x')
        client = self.client.__class__()
        token = RefreshToken.for_user(other)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.post(
            f'/api/approvals/pending-changes/{pending.id}/resubmit/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        pending.refresh_from_db()
        self.assertEqual(pending.status, PendingChange.STATUS_REJECTED)

    def test_cannot_resubmit_while_still_pending(self):
        pending = self._queue_price_change()
        resp = self.client.post(
            f'/api/approvals/pending-changes/{pending.id}/resubmit/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
