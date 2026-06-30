"""Maker-checker resubmit flow for rejected past sales."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_BACKFILL
from products.models import Product
from sales.backfill_policy import user_may_pick_backfill_served_by
from settings.models import StoreSettings


class BackfillResubmitAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.manager_user = User.objects.create_user(username='resubmit_mgr', password='mgr123')
        UserProfile.objects.create(
            user=cls.manager_user,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        cls.checker_user = User.objects.create_user(
            username='resubmit_checker',
            password='chk123',
            is_staff=True,
        )
        UserProfile.objects.create(
            user=cls.checker_user,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.sales_user = User.objects.create_user(username='resubmit_sales', password='sales123')
        UserProfile.objects.create(
            user=cls.sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.other_sales = User.objects.create_user(username='other_sales', password='sales123')
        UserProfile.objects.create(
            user=cls.other_sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.product = Product.objects.create(
            name='Eraser',
            sku='ER-01',
            price='25.00',
            cost='10.00',
            stock_quantity=40,
            track_stock=True,
        )

    def setUp(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.backfill_maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

        self.sales_client = self._client(self.sales_user)
        self.other_sales_client = self._client(self.other_sales)
        self.manager_client = self._client(self.manager_user)
        self.checker_client = self._client(self.checker_user)

    @staticmethod
    def _client(user):
        client = APIClient()
        token = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def _payload(self, **overrides):
        occurred = timezone.now() - timedelta(days=1)
        data = {
            'occurred_at': occurred.isoformat(),
            'backfill_reason': 'Offline sale needs recording now',
            'sale_type': 'pos',
            'payment_method': 'cash',
            'amount_paid': '25.00',
            'acknowledge_stock_warnings': True,
            'items': [
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'unit_price': '25.00',
                }
            ],
        }
        data.update(overrides)
        return data

    def _queue_backfill(self, client=None):
        client = client or self.sales_client
        res = client.post('/api/sales/backfill/', self._payload(), format='json')
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED, res.content)
        return res.data['pending_change']['id']

    def test_my_submissions_lists_only_own_rows(self):
        pending_id = self._queue_backfill()
        self.checker_client.post(
            f'/api/approvals/pending-changes/{pending_id}/reject/',
            {'rejection_reason': 'Fix the date'},
            format='json',
        )

        mine = self.sales_client.get(
            '/api/approvals/pending-changes/my-submissions/',
            {'status': 'rejected', 'action_type': ACTION_SALE_BACKFILL},
        )
        self.assertEqual(mine.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mine.data), 1)
        self.assertEqual(mine.data[0]['id'], pending_id)
        self.assertEqual(mine.data[0]['rejection_reason'], 'Fix the date')

        other = self.other_sales_client.get(
            '/api/approvals/pending-changes/my-submissions/',
            {'status': 'rejected', 'action_type': ACTION_SALE_BACKFILL},
        )
        self.assertEqual(other.status_code, status.HTTP_200_OK)
        self.assertEqual(len(other.data), 0)

    def test_maker_can_retrieve_own_rejected_submission(self):
        pending_id = self._queue_backfill()
        self.checker_client.post(
            f'/api/approvals/pending-changes/{pending_id}/reject/',
            {'rejection_reason': 'Wrong payment method'},
            format='json',
        )

        detail = self.sales_client.get(f'/api/approvals/pending-changes/{pending_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['status'], PendingChange.STATUS_REJECTED)
        self.assertIn('apply_payload', detail.data)

    def test_maker_cannot_retrieve_someone_elses_submission(self):
        pending_id = self._queue_backfill()
        denied = self.other_sales_client.get(f'/api/approvals/pending-changes/{pending_id}/')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_resubmit_requires_rejected_status(self):
        pending_id = self._queue_backfill()
        res = self.sales_client.post(
            '/api/sales/backfill/',
            self._payload(resubmit_of=pending_id),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', res.data)

    def test_resubmit_rejected_only_by_maker(self):
        pending_id = self._queue_backfill()
        self.checker_client.post(
            f'/api/approvals/pending-changes/{pending_id}/reject/',
            {'rejection_reason': 'Please correct items'},
            format='json',
        )

        denied = self.other_sales_client.post(
            '/api/sales/backfill/',
            self._payload(
                backfill_reason='Another user trying to resubmit',
                resubmit_of=pending_id,
            ),
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

        ok = self.sales_client.post(
            '/api/sales/backfill/',
            self._payload(
                backfill_reason='Corrected after rejection review',
                resubmit_of=pending_id,
            ),
            format='json',
        )
        self.assertEqual(ok.status_code, status.HTTP_202_ACCEPTED, ok.content)
        change = PendingChange.objects.get(pk=pending_id)
        self.assertEqual(change.status, PendingChange.STATUS_PENDING)
        self.assertEqual(change.apply_payload.get('backfill_reason'), 'Corrected after rejection review')

    def test_invalid_resubmit_id_returns_400(self):
        res = self.sales_client.post(
            '/api/sales/backfill/',
            self._payload(resubmit_of='not-a-number'),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_can_attribute_served_by_on_backfill(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

        res = self.manager_client.post(
            '/api/sales/backfill/',
            self._payload(served_by_id=self.sales_user.id),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        self.assertEqual(res.data['served_by'], self.sales_user.id)

    def test_resubmit_missing_pending_id_returns_400(self):
        res = self.sales_client.post(
            '/api/sales/backfill/',
            self._payload(resubmit_of=999999),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checker_can_retrieve_any_pending_backfill(self):
        pending_id = self._queue_backfill()
        detail = self.checker_client.get(f'/api/approvals/pending-changes/{pending_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_sales_user_cannot_list_checker_queue(self):
        res = self.sales_client.get('/api/approvals/pending-changes/pending/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_resubmit_blocked_when_backfill_maker_checker_off(self):
        pending_id = self._queue_backfill()
        self.checker_client.post(
            f'/api/approvals/pending-changes/{pending_id}/reject/',
            {'rejection_reason': 'Fix it'},
            format='json',
        )
        store = StoreSettings.load()
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['backfill_maker_checker_enabled'])
        res = self.sales_client.post(
            '/api/sales/backfill/',
            self._payload(
                backfill_reason='Trying to resubmit without MC',
                resubmit_of=pending_id,
            ),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_queue_backfill_rejected_when_maker_checker_disabled(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])
        from approvals.backfill_integration import queue_sale_backfill
        from django.test import RequestFactory

        request = RequestFactory().post('/api/sales/backfill/')
        request.user = self.sales_user
        with self.assertRaises(ValidationError):
            queue_sale_backfill(
                request,
                {
                    'occurred_at': timezone.now() - timedelta(days=1),
                    'backfill_reason': 'Should not queue when MC off',
                    'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '1'}],
                },
            )
