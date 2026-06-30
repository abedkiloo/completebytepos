from datetime import timedelta
from decimal import Decimal

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
from inventory.models import StockMovement
from products.models import Product
from sales.backfill_policy import (
    backfill_max_days,
    get_backfill_stock_warnings,
    resolve_backfill_served_by,
    user_may_pick_backfill_served_by,
    validate_backfill_occurred_at,
    validate_backfill_reason,
)
from settings.models import StoreSettings
from utils.tests.api_test_base import ManagerAPITestCase


class BackfillPolicyTests(TestCase):
    def test_reason_min_length(self):
        with self.assertRaises(Exception):
            validate_backfill_reason('short')
        self.assertEqual(
            validate_backfill_reason('Forgot during busy Saturday'),
            'Forgot during busy Saturday',
        )

    def test_occurred_at_within_window(self):
        now = timezone.now()
        validate_backfill_occurred_at(now - timedelta(days=5))
        with self.assertRaises(Exception):
            validate_backfill_occurred_at(now - timedelta(days=backfill_max_days() + 1))
        with self.assertRaises(Exception):
            validate_backfill_occurred_at(now + timedelta(days=1))


class BackfillStockWarningTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Pen',
            sku='PEN-01',
            price='50.00',
            cost='20.00',
            stock_quantity=20,
            track_stock=True,
        )

    def test_warns_when_adjustment_after_sale_date(self):
        occurred = timezone.now() - timedelta(days=5)
        StockMovement.objects.create(
            product=self.product,
            movement_type='adjustment',
            quantity=5,
            notes='Stock count',
        )
        warnings = get_backfill_stock_warnings(
            occurred,
            [{'product_id': self.product.id, 'quantity': 1}],
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn('Pen', warnings[0]['message'])


class SaleBackfillAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])
        self.product = Product.objects.create(
            name='Notebook',
            sku='NB-01',
            price='100.00',
            cost='50.00',
            stock_quantity=50,
            track_stock=True,
        )

    def test_backfill_queues_for_approval_when_maker_checker_on(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.backfill_maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])
        occurred = timezone.now() - timedelta(days=3)
        res = self.client.post(
            '/api/sales/backfill/',
            {
                'occurred_at': occurred.isoformat(),
                'backfill_reason': 'Sold offline during power outage',
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'served_by_id': self.manager_user.id,
                'acknowledge_stock_warnings': True,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 202, res.content)
        self.assertIn('pending_change', res.data)

    def test_backfill_creates_sale_with_historical_date(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])
        occurred = timezone.now() - timedelta(days=3)
        res = self.client.post(
            '/api/sales/backfill/',
            {
                'occurred_at': occurred.isoformat(),
                'backfill_reason': 'Sold offline during power outage',
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': '200.00',
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 2,
                        'unit_price': '100.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        data = res.data
        self.assertEqual(data['entry_source'], 'backfill')
        self.assertTrue(data['is_late_entry'])
        self.assertEqual(float(data['total']), 200.0)
        self.assertEqual(data['served_by'], self.manager_user.id)

    def test_preflight_returns_stock_warnings(self):
        occurred = timezone.now() - timedelta(days=4)
        StockMovement.objects.create(
            product=self.product,
            movement_type='adjustment',
            quantity=2,
        )
        res = self.client.post(
            '/api/sales/backfill-preflight/',
            {
                'occurred_at': occurred.isoformat(),
                'items': [{'product_id': self.product.id, 'quantity': 1}],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(len(res.data['warnings']), 1)

    def test_backfill_blocks_without_stock_acknowledgement(self):
        occurred = timezone.now() - timedelta(days=4)
        StockMovement.objects.create(
            product=self.product,
            movement_type='adjustment',
            quantity=2,
        )
        res = self.client.post(
            '/api/sales/backfill/',
            {
                'occurred_at': occurred.isoformat(),
                'backfill_reason': 'Sold offline during power outage',
                'sale_type': 'pos',
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('stock_warnings', res.data)

    def test_csv_import_creates_sale(self):
        occurred = timezone.now() - timedelta(days=2)
        csv_body = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id\n'
            f'R1,{occurred.isoformat()},Sold offline during outage,{self.product.sku},1,100.00,'
            'cash,100.00,pos,,,\n'
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        res = self.client.post(
            '/api/sales/backfill-import-csv/',
            {'file': SimpleUploadedFile('sales.csv', csv_body.encode('utf-8'), 'text/csv')},
            format='multipart',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['created'], 1)
        self.assertEqual(res.data['errors'], [])


class BackfillPolicyServedByTests(TestCase):
    def test_unauthenticated_user_cannot_pick_served_by(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(user_may_pick_backfill_served_by(AnonymousUser()))
        self.assertEqual(resolve_backfill_served_by(AnonymousUser(), 5), AnonymousUser())

    def test_validate_backfill_occurred_at_requires_value(self):
        with self.assertRaises(Exception):
            validate_backfill_occurred_at(None)

    def test_get_backfill_stock_warnings_skips_untracked_products(self):
        product = Product.objects.create(
            name='Service item',
            sku='SVC-1',
            price='10.00',
            cost='5.00',
            stock_quantity=0,
            track_stock=False,
        )
        occurred = timezone.now() - timedelta(days=3)
        StockMovement.objects.create(
            product=product,
            movement_type='adjustment',
            quantity=1,
        )
        self.assertEqual(
            get_backfill_stock_warnings(
                occurred,
                [{'product_id': product.id, 'quantity': 1}],
            ),
            [],
        )

    def test_get_backfill_stock_warnings_returns_empty_without_occurred_at(self):
        self.assertEqual(get_backfill_stock_warnings(None, []), [])

    def test_superuser_may_pick_backfill_served_by(self):
        admin = User.objects.create_superuser(username='su_pick', password='x', email='su@test.com')
        self.assertTrue(user_may_pick_backfill_served_by(admin))


class BackfillIntegrationUnitTests(TestCase):
    def test_summarize_items_includes_variant_ids(self):
        from approvals.backfill_integration import _build_backfill_summary
        from django.utils import timezone

        user = User.objects.create_user(username='summary_user', password='x')
        summary = _build_backfill_summary(
            {
                'occurred_at': timezone.now(),
                'served_by_id': user.id,
                'items': [{'product_id': 1, 'variant_id': 9, 'quantity': 2}],
                '_preview_total': Decimal('20.00'),
            }
        )
        self.assertIn('variant #9', summary['lines'])
        self.assertEqual(summary['served_by'], 'summary_user')

    def test_queue_sale_backfill_requires_items(self):
        from approvals.backfill_integration import queue_sale_backfill
        from django.test import RequestFactory

        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.backfill_maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

        request = RequestFactory().post('/api/sales/backfill/')
        request.user = User.objects.create_user(username='queue_user', password='x')
        with self.assertRaises(ValidationError):
            queue_sale_backfill(
                request,
                {
                    'occurred_at': timezone.now() - timedelta(days=1),
                    'backfill_reason': 'Missing line items here',
                    'items': [],
                },
            )

    def test_resubmit_rejects_non_backfill_change(self):
        from approvals.backfill_integration import resubmit_sale_backfill
        from approvals.models import PendingChange
        from django.test import RequestFactory

        user = User.objects.create_user(username='resubmit_user', password='x')
        change = PendingChange.objects.create(
            action_type='product_price',
            entity_type='products.Product',
            entity_id='1',
            entity_repr='Product',
            status=PendingChange.STATUS_REJECTED,
            made_by=user,
            reason='test',
            original_values={},
            proposed_values={},
            apply_payload={},
        )
        request = RequestFactory().post('/api/sales/backfill/')
        request.user = user
        with self.assertRaises(ValidationError):
            resubmit_sale_backfill(
                request,
                change,
                {
                    'occurred_at': timezone.now() - timedelta(days=1),
                    'backfill_reason': 'Should not apply here',
                    'items': [{'product_id': 1, 'quantity': 1, 'unit_price': '1'}],
                },
            )

    def test_resubmit_requires_items(self):
        from approvals.backfill_integration import resubmit_sale_backfill
        from approvals.models import PendingChange
        from django.test import RequestFactory

        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.backfill_maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

        user = User.objects.create_user(username='empty_items_user', password='x')
        change = PendingChange.objects.create(
            action_type='sale_backfill',
            entity_type='sales.SaleBackfill',
            entity_id='new',
            entity_repr='Past sale',
            status=PendingChange.STATUS_REJECTED,
            made_by=user,
            reason='test',
            original_values={},
            proposed_values={},
            apply_payload={},
        )
        request = RequestFactory().post('/api/sales/backfill/')
        request.user = user
        with self.assertRaises(ValidationError):
            resubmit_sale_backfill(
                request,
                change,
                {
                    'occurred_at': timezone.now() - timedelta(days=1),
                    'backfill_reason': 'No items on resubmit',
                    'items': [],
                },
            )


class BackfillResubmitAndServedByTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.manager_user = User.objects.create_user(username='bf_mgr', password='mgr123')
        cls.manager_role = Role.objects.get(name=ROLE_MANAGER)
        UserProfile.objects.create(
            user=cls.manager_user,
            role='manager',
            custom_role=cls.manager_role,
            is_active=True,
        )
        cls.checker_user = User.objects.create_user(
            username='bf_checker',
            password='chk123',
            is_staff=True,
        )
        checker_role = Role.objects.get(name=ROLE_SUPER_ADMIN)
        UserProfile.objects.create(
            user=cls.checker_user,
            role='super_admin',
            custom_role=checker_role,
            is_active=True,
        )
        cls.sales_user = User.objects.create_user(username='bf_sales', password='sales123')
        cls.sales_role = Role.objects.get(name=ROLE_SALES)
        UserProfile.objects.create(
            user=cls.sales_user,
            role='cashier',
            custom_role=cls.sales_role,
            is_active=True,
        )
        cls.product = Product.objects.create(
            name='Marker',
            sku='MK-01',
            price='50.00',
            cost='20.00',
            stock_quantity=30,
            track_stock=True,
        )

    def setUp(self):
        self.sales_client = APIClient()
        sales_token = RefreshToken.for_user(self.sales_user)
        self.sales_client.credentials(HTTP_AUTHORIZATION=f'Bearer {sales_token.access_token}')
        self.manager_client = APIClient()
        mgr_token = RefreshToken.for_user(self.manager_user)
        self.manager_client.credentials(HTTP_AUTHORIZATION=f'Bearer {mgr_token.access_token}')
        self.checker_client = APIClient()
        checker_token = RefreshToken.for_user(self.checker_user)
        self.checker_client.credentials(HTTP_AUTHORIZATION=f'Bearer {checker_token.access_token}')

    def _backfill_payload(self, **overrides):
        occurred = timezone.now() - timedelta(days=2)
        payload = {
            'occurred_at': occurred.isoformat(),
            'backfill_reason': 'Sold offline during busy period',
            'sale_type': 'pos',
            'payment_method': 'cash',
            'amount_paid': '50.00',
            'acknowledge_stock_warnings': True,
            'items': [
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'unit_price': '50.00',
                }
            ],
        }
        payload.update(overrides)
        return payload

    def test_resubmit_rejected_backfill(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.backfill_maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

        create = self.sales_client.post(
            '/api/sales/backfill/',
            self._backfill_payload(),
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_202_ACCEPTED, create.content)
        pending_id = create.data['pending_change']['id']

        reject = self.checker_client.post(
            f'/api/approvals/pending-changes/{pending_id}/reject/',
            {'rejection_reason': 'Wrong date — please fix'},
            format='json',
        )
        self.assertEqual(reject.status_code, status.HTTP_200_OK, reject.content)

        pending = PendingChange.objects.get(pk=pending_id)
        self.assertEqual(pending.status, PendingChange.STATUS_REJECTED)

        resubmit = self.sales_client.post(
            '/api/sales/backfill/',
            self._backfill_payload(
                backfill_reason='Corrected date after manager review',
                resubmit_of=pending_id,
            ),
            format='json',
        )
        self.assertEqual(resubmit.status_code, status.HTTP_202_ACCEPTED, resubmit.content)
        pending.refresh_from_db()
        self.assertEqual(pending.status, PendingChange.STATUS_PENDING)
        self.assertEqual(pending.rejection_reason, '')

        mine = self.sales_client.get(
            '/api/approvals/pending-changes/my-submissions/',
            {'status': 'rejected', 'action_type': 'sale_backfill'},
        )
        self.assertEqual(mine.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mine.data), 0)

    def test_served_by_forced_for_sales_user(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

        res = self.sales_client.post(
            '/api/sales/backfill/',
            self._backfill_payload(served_by_id=self.manager_user.id),
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        self.assertEqual(res.data['served_by'], self.sales_user.id)

    def test_resolve_backfill_served_by_policy(self):
        self.assertEqual(
            resolve_backfill_served_by(self.sales_user, self.manager_user.id),
            self.sales_user,
        )
        picked = resolve_backfill_served_by(self.manager_user, self.sales_user.id)
        self.assertEqual(picked.id, self.sales_user.id)

    def test_user_may_pick_backfill_served_by_superuser(self):
        self.assertTrue(user_may_pick_backfill_served_by(self.checker_user))

    def test_resolve_backfill_served_by_ignores_invalid_staff_id(self):
        self.assertEqual(
            resolve_backfill_served_by(self.manager_user, 999999),
            self.manager_user,
        )
