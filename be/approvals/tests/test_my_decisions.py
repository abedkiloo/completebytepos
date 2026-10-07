"""Checker accountability trail: my-decisions lists decided rows with filters."""

from datetime import datetime

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
        rows = resp.data['results']
        ids = [row['id'] for row in rows]
        self.assertIn(approved.id, ids)
        self.assertIn(rejected.id, ids)
        self.assertEqual(resp.data['count'], 2)
        self.assertEqual(len(ids), 2)

        approved_row = next(row for row in rows if row['id'] == approved.id)
        self.assertEqual(approved_row['status'], PendingChange.STATUS_APPROVED)
        self.assertEqual(approved_row['checked_by'], self.manager_user.id)
        self.assertIsNotNone(approved_row['checked_at'])
        self.assertEqual(approved_row['reason'], 'Supplier list update')

        rejected_row = next(row for row in rows if row['id'] == rejected.id)
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
        approved_rows = only_approved.data['results']
        self.assertTrue(all(r['status'] == 'approved' for r in approved_rows))
        self.assertIn(approved.id, [r['id'] for r in approved_rows])

        only_sales = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'action_type': ACTION_SALE_COMPLETE},
        )
        self.assertEqual(only_sales.status_code, status.HTTP_200_OK)
        self.assertEqual([r['id'] for r in only_sales.data['results']], [sale.id])

        multi = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'action_type': f'{ACTION_PRODUCT_PRICE},{ACTION_SALE_COMPLETE}'},
        )
        self.assertEqual(multi.status_code, status.HTTP_200_OK)
        multi_ids = {r['id'] for r in multi.data['results']}
        self.assertIn(approved.id, multi_ids)
        self.assertIn(sale.id, multi_ids)

    def test_my_decisions_paginates(self):
        for _ in range(12):
            self._make_decision(
                checker=self.manager_user,
                status_value=PendingChange.STATUS_APPROVED,
            )
        page1 = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'page': 1, 'page_size': 5},
        )
        self.assertEqual(page1.status_code, status.HTTP_200_OK, page1.data)
        self.assertEqual(page1.data['count'], 12)
        self.assertEqual(len(page1.data['results']), 5)

        page2 = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'page': 2, 'page_size': 5},
        )
        self.assertEqual(page2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(page2.data['results']), 5)
        page1_ids = {r['id'] for r in page1.data['results']}
        page2_ids = {r['id'] for r in page2.data['results']}
        self.assertFalse(page1_ids & page2_ids)

    def test_my_decisions_shows_all_checkers_by_default(self):
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
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(mine.id, ids)
        self.assertIn(theirs.id, ids)

        mine_only = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'scope': 'mine'},
        )
        self.assertEqual(mine_only.status_code, status.HTTP_200_OK)
        mine_ids = [r['id'] for r in mine_only.data['results']]
        self.assertIn(mine.id, mine_ids)
        self.assertNotIn(theirs.id, mine_ids)

    def test_my_decisions_date_and_people_filters(self):
        early = self._make_decision(
            checker=self.manager_user,
            status_value=PendingChange.STATUS_APPROVED,
        )
        PendingChange.objects.filter(pk=early.pk).update(
            checked_at=timezone.make_aware(datetime(2020, 1, 15, 12, 0, 0)),
        )
        recent = self._make_decision(
            checker=self.other_manager,
            status_value=PendingChange.STATUS_APPROVED,
        )
        other_requester = User.objects.create_user('dec_sales2', password='x')
        UserProfile.objects.create(
            user=other_requester,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        by_other = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id='9',
            entity_repr='Other requester',
            original_values={},
            proposed_values={'price': '11'},
            reason='x',
            status=PendingChange.STATUS_APPROVED,
            made_by=other_requester,
            checked_by=self.manager_user,
            checked_at=timezone.now(),
        )

        by_date = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {
                'date_from': timezone.localdate().isoformat(),
                'date_to': timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(by_date.status_code, status.HTTP_200_OK)
        date_ids = {r['id'] for r in by_date.data['results']}
        self.assertIn(recent.id, date_ids)
        self.assertIn(by_other.id, date_ids)
        self.assertNotIn(early.id, date_ids)

        by_checker = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'checked_by': self.other_manager.id},
        )
        self.assertEqual(by_checker.status_code, status.HTTP_200_OK)
        self.assertEqual([r['id'] for r in by_checker.data['results']], [recent.id])

        by_requester = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'made_by': other_requester.id},
        )
        self.assertEqual(by_requester.status_code, status.HTTP_200_OK)
        self.assertEqual([r['id'] for r in by_requester.data['results']], [by_other.id])

        people = self.client.get('/api/approvals/pending-changes/decision-people/')
        self.assertEqual(people.status_code, status.HTTP_200_OK)
        requester_ids = {p['id'] for p in people.data['requesters']}
        checker_ids = {p['id'] for p in people.data['checkers']}
        self.assertIn(self.sales.id, requester_ids)
        self.assertIn(other_requester.id, requester_ids)
        self.assertIn(self.manager_user.id, checker_ids)
        self.assertIn(self.other_manager.id, checker_ids)

    def test_sales_cannot_open_my_decisions(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.sales)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.get('/api/approvals/pending-changes/my-decisions/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
