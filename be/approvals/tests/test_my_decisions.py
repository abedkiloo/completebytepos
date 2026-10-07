"""Checker accountability trail: my-decisions lists rows this user decided."""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import ACTION_PRODUCT_PRICE, ACTION_SALE_COMPLETE
from utils.tests.api_test_base import ManagerAPITestCase


class MyDecisionsAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.sales = User.objects.create_user('dec_sales', password='x')
        UserProfile.objects.create(
            user=cls.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.other_manager = User.objects.create_user('dec_other_mgr', password='x')
        UserProfile.objects.create(
            user=cls.other_manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )

    def _make_decision(self, *, checker, status_value, rejection_reason='', action_type=ACTION_PRODUCT_PRICE):
        return PendingChange.objects.create(
            action_type=action_type,
            entity_type='products.Product',
            entity_id='1',
            entity_repr='Widget',
            original_values={'price': '10'},
            proposed_values={'price': '12'},
            reason='Supplier list update',
            status=status_value,
            made_by=self.sales,
            checked_by=checker,
            checked_at=timezone.now(),
            rejection_reason=rejection_reason,
        )

    def test_my_decisions_lists_approved_and_rejected_by_me(self):
        approved = self._make_decision(
            checker=self.manager_user,
            status_value=PendingChange.STATUS_APPROVED,
        )
        rejected = self._make_decision(
            checker=self.manager_user,
            status_value=PendingChange.STATUS_REJECTED,
            rejection_reason='Price too high',
        )
        # Still pending — must not appear.
        PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id='2',
            entity_repr='Other',
            original_values={},
            proposed_values={'price': '9'},
            reason='Wait',
            status=PendingChange.STATUS_PENDING,
            made_by=self.sales,
        )

        resp = self.client.get('/api/approvals/pending-changes/my-decisions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        ids = [row['id'] for row in resp.data]
        self.assertIn(approved.id, ids)
        self.assertIn(rejected.id, ids)
        self.assertEqual(len(ids), 2)

        approved_row = next(row for row in resp.data if row['id'] == approved.id)
        self.assertEqual(approved_row['status'], PendingChange.STATUS_APPROVED)
        self.assertEqual(approved_row['checked_by'], self.manager_user.id)
        self.assertIsNotNone(approved_row['checked_at'])
        self.assertEqual(approved_row['reason'], 'Supplier list update')

        rejected_row = next(row for row in resp.data if row['id'] == rejected.id)
        self.assertEqual(rejected_row['status'], PendingChange.STATUS_REJECTED)
        self.assertEqual(rejected_row['rejection_reason'], 'Price too high')

    def test_my_decisions_status_and_action_filters(self):
        approved = self._make_decision(
            checker=self.manager_user,
            status_value=PendingChange.STATUS_APPROVED,
        )
        self._make_decision(
            checker=self.manager_user,
            status_value=PendingChange.STATUS_REJECTED,
            rejection_reason='No',
        )
        sale = self._make_decision(
            checker=self.manager_user,
            status_value=PendingChange.STATUS_APPROVED,
            action_type=ACTION_SALE_COMPLETE,
        )

        only_approved = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'status': 'approved'},
        )
        self.assertEqual(only_approved.status_code, status.HTTP_200_OK)
        self.assertTrue(all(r['status'] == 'approved' for r in only_approved.data))
        self.assertIn(approved.id, [r['id'] for r in only_approved.data])

        only_sales = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'action_type': ACTION_SALE_COMPLETE},
        )
        self.assertEqual(only_sales.status_code, status.HTTP_200_OK)
        self.assertEqual([r['id'] for r in only_sales.data], [sale.id])

    def test_my_decisions_excludes_other_checkers_work(self):
        mine = self._make_decision(
            checker=self.manager_user,
            status_value=PendingChange.STATUS_APPROVED,
        )
        theirs = self._make_decision(
            checker=self.other_manager,
            status_value=PendingChange.STATUS_APPROVED,
        )

        resp = self.client.get('/api/approvals/pending-changes/my-decisions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in resp.data]
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids)

    def test_sales_cannot_open_my_decisions(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.sales)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.get('/api/approvals/pending-changes/my-decisions/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
