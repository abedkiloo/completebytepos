"""
TDD contract: maker-checker for sensitive product, stock, and settings writes.

Tests define behavior — implementations must satisfy them without weakening assertions.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AuditLog, Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import (
    ACTION_CATEGORY_DEACTIVATE,
    ACTION_CATEGORY_DELETE,
    ACTION_PRODUCT_DEACTIVATE,
    ACTION_PRODUCT_DELETE,
    ACTION_PRODUCT_PRICE,
    ACTION_PRODUCT_STOCK,
    ACTION_PRODUCT_TAX,
    ACTION_PRODUCT_UNIT,
    ACTION_STOCK_ADJUST,
    ACTION_STOCK_PURCHASE,
    ACTION_STOCK_TRANSFER,
)
from approvals.effective import approved_sellable_stock_quantity
from settings.test_utils import enable_multi_branch_support
from products.models import Category, Color, Product, ProductVariant, Size
from sales.models import Sale
from settings.models import StoreSettings
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


def _enable_maker_checker(**kwargs):
    store = StoreSettings.load()
    store.maker_checker_enabled = kwargs.get('enabled', True)
    store.emergency_stock_mode = kwargs.get('emergency', False)
    if kwargs.get('enabled', True):
        store.hide_entity_status_toggles = False
    store.save(
        update_fields=[
            'maker_checker_enabled',
            'emergency_stock_mode',
            'hide_entity_status_toggles',
        ]
    )
    store.refresh_from_db()


def setUpModule():
    _enable_maker_checker(enabled=True)


def tearDownModule():
    _enable_maker_checker(enabled=True)
    from settings.settings_service import SettingsService

    SettingsService.set('products', 'show_status', True)
    SettingsService.invalidate('products')


class MakerCheckerProductTests(ManagerAPITestCase):
    """Manager proposes; live product unchanged until checker approves."""

    def tearDown(self):
        _enable_maker_checker(enabled=True)
        super().tearDown()

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.checker = User.objects.create_user('checker_mc', password='chk123', is_staff=True)
        checker_role = Role.objects.get(name=ROLE_SUPER_ADMIN)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=checker_role,
            is_active=True,
        )
        cls.category = Category.objects.create(name='MC Cat', is_active=True)
        cls.product = Product.objects.create(
            name='MC Product',
            sku='MC-PROD-1',
            category=cls.category,
            price=Decimal('100'),
            cost=Decimal('50'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker()
        store = StoreSettings.load()
        store.hide_entity_status_toggles = False
        store.save(update_fields=['hide_entity_status_toggles'])
        PendingChange.objects.all().delete()
        AuditLog.objects.filter(module='approvals').delete()

    def _checker_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_maker_price_change_leaves_live_data_unchanged(self):
        response = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '150.00', 'reason': 'Market adjustment'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('100'))
        pending = PendingChange.objects.get(status=PendingChange.STATUS_PENDING)
        self.assertEqual(pending.action_type, ACTION_PRODUCT_PRICE)
        self.assertEqual(pending.proposed_values.get('price'), '150.00')

    def test_maker_cost_change_exposes_proposed_value_in_product_payload(self):
        response = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'cost': '72.00', 'reason': 'Supplier invoice'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.cost, Decimal('50'))
        product_payload = response.data.get('product') or {}
        pending = product_payload.get('pending_approval') or {}
        self.assertTrue(pending.get('pending_price'))
        self.assertEqual(pending.get('proposed_values', {}).get('cost'), '72.00')

    def test_checker_approves_updates_live_price(self):
        self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '150.00', 'reason': 'Market adjustment'},
            format='json',
        )
        pending = PendingChange.objects.get(status=PendingChange.STATUS_PENDING)
        checker = self._checker_client()
        resp = checker.post(f'/api/approvals/pending-changes/{pending.id}/approve/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('150'))
        pending.refresh_from_db()
        self.assertEqual(pending.status, PendingChange.STATUS_APPROVED)
        self.assertTrue(
            AuditLog.objects.filter(module='approvals', action='pending_approve').exists()
        )

    def test_checker_reject_leaves_live_unchanged(self):
        self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '200.00', 'reason': 'Rejected test'},
            format='json',
        )
        pending = PendingChange.objects.get()
        checker = self._checker_client()
        resp = checker.post(
            f'/api/approvals/pending-changes/{pending.id}/reject/',
            {'rejection_reason': 'Price too high'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('100'))
        pending.refresh_from_db()
        self.assertEqual(pending.status, PendingChange.STATUS_REJECTED)
        self.assertEqual(pending.rejection_reason, 'Price too high')

    def test_pos_search_uses_approved_price_not_pending(self):
        self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '999.00', 'reason': 'Should not appear at POS'},
            format='json',
        )
        search = self.client.get('/api/products/search/', {'q': 'MC Product'})
        self.assertEqual(search.status_code, status.HTTP_200_OK)
        row = next(r for r in search.data if r['id'] == self.product.id)
        self.assertEqual(str(row['price']), '100.00')
        self.assertTrue(row.get('pending_approval', {}).get('pending_price'))

    def test_tax_rate_change_queues_product_tax_action(self):
        self.product.tax_rate = Decimal('16')
        self.product.save(update_fields=['tax_rate'])
        resp = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'tax_rate': '8', 'reason': 'VAT category change'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.tax_rate, Decimal('16'))
        pending = PendingChange.objects.get(action_type=ACTION_PRODUCT_TAX)
        self.assertEqual(str(pending.proposed_values.get('tax_rate')), '8.00')

    def test_unit_change_queues_product_unit_action(self):
        self.product.unit = 'pcs'
        self.product.save(update_fields=['unit'])
        resp = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'unit': 'kg', 'reason': 'Weigh-scale sales'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.unit, 'pcs')
        pending = PendingChange.objects.get(action_type=ACTION_PRODUCT_UNIT)
        self.assertEqual(pending.proposed_values.get('unit'), 'kg')

    def test_price_and_stock_patch_share_batch_id(self):
        resp = self.client.patch(
            f'/api/products/{self.product.id}/',
            {
                'price': '110.00',
                'stock_quantity': 40,
                'reason': 'Reprice and recount',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        pending = PendingChange.objects.filter(status=PendingChange.STATUS_PENDING)
        self.assertEqual(pending.count(), 2)
        batch_ids = {p.batch_id for p in pending if p.batch_id}
        self.assertEqual(len(batch_ids), 1)
        self.assertTrue(batch_ids.pop())
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('100'))
        self.assertEqual(self.product.stock_quantity, 50)

    def test_non_sensitive_name_update_applies_immediately(self):
        resp = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'name': 'MC Product Renamed'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'MC Product Renamed')
        self.assertFalse(PendingChange.objects.exists())

    def test_maker_cannot_approve_own_change(self):
        self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '120.00', 'reason': 'Self approve'},
            format='json',
        )
        pending = PendingChange.objects.get()
        resp = self.client.post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('100'))

    def test_deactivate_pending_keeps_product_active_for_pos(self):
        resp = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'is_active': False, 'reason': 'End of season'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)
        search = self.client.get('/api/products/search/', {'q': 'MC Product'})
        row = next(r for r in search.data if r['id'] == self.product.id)
        self.assertTrue(row['is_active'])
        self.assertTrue(row.get('pending_approval', {}).get('pending_deactivation'))
        pending = PendingChange.objects.get(action_type=ACTION_PRODUCT_DEACTIVATE)
        checker = self._checker_client()
        checker.post(f'/api/approvals/pending-changes/{pending.id}/approve/', {}, format='json')
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_delete_pending_keeps_product_until_checker_approves(self):
        product_id = self.product.id
        resp = self.client.delete(
            f'/api/products/{product_id}/',
            {'reason': 'Duplicate SKU cleanup'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.assertTrue(Product.objects.filter(pk=product_id).exists())
        pending = PendingChange.objects.get(action_type=ACTION_PRODUCT_DELETE)
        checker = self._checker_client()
        approve = checker.post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.assertFalse(Product.objects.filter(pk=product_id).exists())

    def test_extreme_price_requires_confirmation_on_approve(self):
        self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '500.00', 'reason': 'Big jump'},
            format='json',
        )
        pending = PendingChange.objects.get()
        checker = self._checker_client()
        blocked = checker.post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        ok = checker.post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {'extreme_price_confirmed': True},
            format='json',
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('500'))


class MakerCheckerNegativeStockTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.checker = User.objects.create_user('chk_neg', password='x', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cat = Category.objects.create(name='Neg', is_active=True)
        cls.product = Product.objects.create(
            name='Neg Stock Product',
            sku='MC-NEG-1',
            category=cat,
            price=Decimal('10'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker()
        PendingChange.objects.all().delete()

    def _checker_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_approve_negative_adjust_blocked(self):
        self.client.post(
            '/api/inventory/adjust/',
            {
                'product_id': self.product.id,
                'quantity': -8,
                'notes': 'Over-adjust',
                'reason': 'Count error',
            },
            format='json',
        )
        pending = PendingChange.objects.get(action_type=ACTION_STOCK_ADJUST)
        resp = self._checker_client().post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)


class MakerCheckerStockTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Stock MC', is_active=True)
        cls.product = Product.objects.create(
            name='Stock MC Product',
            sku='MC-STK-1',
            category=cls.category,
            price=Decimal('10'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker()
        PendingChange.objects.all().delete()

    def test_stock_adjust_pending_does_not_move_live_stock(self):
        resp = self.client.post(
            '/api/inventory/adjust/',
            {
                'product_id': self.product.id,
                'quantity': 5,
                'notes': 'audit adjust',
                'reason': 'Cycle count',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertTrue(
            PendingChange.objects.filter(action_type=ACTION_STOCK_ADJUST).exists()
        )

    def test_emergency_mode_positive_adjust_applies_immediately(self):
        _enable_maker_checker(emergency=True)
        resp = self.client.post(
            '/api/inventory/adjust/',
            {
                'product_id': self.product.id,
                'quantity': 3,
                'notes': 'emergency',
                'reason': 'Zero stock emergency',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 23)

    def test_stock_purchase_pending_until_checker_approves(self):
        sync_default_roles()
        checker = User.objects.create_user('chk_purchase', password='x', is_staff=True)
        UserProfile.objects.create(
            user=checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        resp = self.client.post(
            '/api/inventory/purchase/',
            {
                'product_id': self.product.id,
                'quantity': 4,
                'unit_cost': '8.00',
                'notes': 'PO arrival',
                'reason': 'Supplier delivery',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        pending = PendingChange.objects.get(action_type=ACTION_STOCK_PURCHASE)
        client = self.client.__class__()
        token = RefreshToken.for_user(checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        approve = client.post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK, approve.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 24)


class MakerCheckerTransferTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        enable_multi_branch_support()
        cls.tenant, cls.branch_a, cls.branch_b = cls.create_tenant_with_branches(
            cls.manager_user,
            code='MCT',
            branch_names=('MC HQ', 'MC Store B'),
        )
        cat = Category.objects.create(name='Xfer', is_active=True)
        cls.product = Product.objects.create(
            name='Xfer Product',
            sku='MC-XFER-1',
            category=cat,
            price=Decimal('10'),
            stock_quantity=30,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        self.set_session_branch(self.tenant, self.branch_a)
        _enable_maker_checker()
        PendingChange.objects.all().delete()

    def test_stock_transfer_pending_does_not_move_stock(self):
        resp = self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 5,
                'to_branch_id': self.branch_b.id,
                'reason': 'Rebalance stores',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 30)
        self.assertTrue(
            PendingChange.objects.filter(action_type=ACTION_STOCK_TRANSFER).exists()
        )


class MakerCheckerBulkAdjustTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Bulk', is_active=True)
        cls.product = Product.objects.create(
            name='Bulk Product',
            sku='MC-BULK-1',
            category=cat,
            price=Decimal('5'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker()
        PendingChange.objects.all().delete()

    def test_bulk_adjust_queues_batch(self):
        resp = self.client.post(
            '/api/inventory/bulk_adjust/',
            {
                'reason': 'Cycle count batch',
                'adjustments': [
                    {'product_id': self.product.id, 'quantity': 2, 'notes': 'line 1'},
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(
            PendingChange.objects.filter(action_type=ACTION_STOCK_ADJUST).count(),
            1,
        )
        self.assertTrue(resp.data.get('batch_id'))


class MakerCheckerDisabledTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Off', is_active=True)
        cls.product = Product.objects.create(
            name='Off Product',
            sku='MC-OFF-1',
            category=cls.category,
            price=Decimal('50'),
            stock_quantity=10,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker(enabled=False)

    def test_price_patch_applies_when_maker_checker_off(self):
        resp = self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '75.00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('75'))


class MakerCheckerAuditTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.checker = User.objects.create_user('checker_audit', password='chk123', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cat = Category.objects.create(name='Aud', is_active=True)
        cls.product = Product.objects.create(
            name='Aud Product',
            sku='MC-AUD-1',
            category=cat,
            price=Decimal('40'),
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker()
        AuditLog.objects.filter(module='approvals').delete()

    def _checker_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_submit_logs_original_and_proposed(self):
        self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '55.00', 'reason': 'Audit trail'},
            format='json',
        )
        row = AuditLog.objects.filter(module='approvals', action='pending_submit').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.changes['original_values']['price'], '40.00')
        self.assertEqual(row.changes['proposed_values']['price'], '55.00')


class MakerCheckerSellableStockTests(ManagerAPITestCase):
    """Pending stock decreases must cap POS/checkout availability (row 15)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Sell', is_active=True)
        cls.product = Product.objects.create(
            name='Sell Cap Product',
            sku='MC-SELL-1',
            category=cat,
            price=Decimal('10'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker()
        PendingChange.objects.all().delete()

    def test_pending_decrease_adjust_caps_sellable_and_list_stock(self):
        self.client.post(
            '/api/inventory/adjust/',
            {
                'product_id': self.product.id,
                'quantity': -12,
                'notes': 'Shrinkage',
                'reason': 'Pending shrink',
            },
            format='json',
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertEqual(approved_sellable_stock_quantity(self.product), 8)

        detail = self.client.get(f'/api/products/{self.product.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['stock_quantity'], 8)
        self.assertTrue(detail.data['pending_approval']['pending_stock'])

    def test_sale_blocked_when_pending_adjust_would_oversell(self):
        from django.core.exceptions import ValidationError
        from sales.services import SaleService

        self.client.post(
            '/api/inventory/adjust/',
            {
                'product_id': self.product.id,
                'quantity': -15,
                'notes': 'Count',
                'reason': 'Pending count down',
            },
            format='json',
        )
        service = SaleService()
        with self.assertRaises(ValidationError) as ctx:
            service.validate_sale_items(
                [{'product_id': self.product.id, 'quantity': 10}],
                check_stock=True,
                user=self.manager_user,
            )
        self.assertIn('Insufficient stock', str(ctx.exception))

    def test_pending_stock_increase_does_not_inflate_sellable(self):
        self.client.patch(
            f'/api/products/{self.product.id}/',
            {'stock_quantity': 100, 'reason': 'Warehouse recount'},
            format='json',
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)
        self.assertEqual(approved_sellable_stock_quantity(self.product), 20)


class MakerCheckerReportsTests(ManagerAPITestCase):
    """Completed sales totals must not include pending price changes."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Rep', is_active=True)
        cls.product = Product.objects.create(
            name='Rep Product',
            sku='MC-REP-1',
            category=cls.category,
            price=Decimal('100'),
            stock_quantity=5,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker()

    def test_pending_price_does_not_alter_existing_sale_line_context(self):
        Sale.objects.create(
            sale_number='S-MC-1',
            total=Decimal('100'),
            subtotal=Decimal('100'),
            status='completed',
            payment_method='cash',
            amount_paid=Decimal('100'),
        )
        self.client.patch(
            f'/api/products/{self.product.id}/',
            {'price': '500.00', 'reason': 'Must not rewrite history'},
            format='json',
        )
        sale = Sale.objects.get(sale_number='S-MC-1')
        self.assertEqual(sale.total, Decimal('100'))


class MakerCheckerVariantTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.checker = User.objects.create_user('chk_var', password='x', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cat = Category.objects.create(name='Var Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Var Parent',
            sku='MC-VAR-P',
            category=cat,
            price=Decimal('100'),
            has_variants=True,
            is_active=True,
        )
        cls.size = Size.objects.create(name='Large', code='L', is_active=True)
        cls.color = Color.objects.create(name='Blue', is_active=True)
        cls.variant = ProductVariant.objects.create(
            product=cls.product,
            size=cls.size,
            color=cls.color,
            sku='MC-VAR-1',
            price=Decimal('100'),
            stock_quantity=25,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _enable_maker_checker()
        PendingChange.objects.all().delete()

    def _checker_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_variant_price_pending_leaves_live_unchanged(self):
        resp = self.client.patch(
            f'/api/products/variants/{self.variant.id}/',
            {'price': '140.00', 'reason': 'Variant promo'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.price, Decimal('100'))
        pending = PendingChange.objects.get(
            entity_type='products.ProductVariant',
            action_type=ACTION_PRODUCT_PRICE,
        )
        self.assertEqual(pending.proposed_values.get('price'), '140.00')

    def test_variant_mrp_pending_leaves_live_unchanged(self):
        self.variant.mrp = Decimal('120')
        self.variant.save(update_fields=['mrp'])
        resp = self.client.patch(
            f'/api/products/variants/{self.variant.id}/',
            {'mrp': '150.00', 'reason': 'List price update'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.mrp, Decimal('120'))
        pending = PendingChange.objects.get(
            entity_type='products.ProductVariant',
            action_type=ACTION_PRODUCT_PRICE,
        )
        self.assertEqual(pending.proposed_values.get('mrp'), '150.00')

    def test_variant_cost_pending_leaves_live_unchanged(self):
        from settings.models import ModuleSetting

        ModuleSetting.objects.update_or_create(
            module='products',
            key='allow_manager_edit_cost',
            defaults={
                'label': 'allow_manager_edit_cost',
                'description': '',
                'default_value': True,
                'value': True,
            },
        )
        self.variant.cost = Decimal('40')
        self.variant.save(update_fields=['cost'])
        resp = self.client.patch(
            f'/api/products/variants/{self.variant.id}/',
            {'cost': '55.00', 'reason': 'Supplier increase'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.cost, Decimal('40'))
        pending = PendingChange.objects.filter(
            entity_type='products.ProductVariant',
            action_type=ACTION_PRODUCT_PRICE,
        ).latest('id')
        self.assertEqual(pending.proposed_values.get('cost'), '55.00')

    def test_variant_stock_pending_caps_sellable(self):
        self.client.patch(
            f'/api/products/variants/{self.variant.id}/',
            {'stock_quantity': 5, 'reason': 'Recount'},
            format='json',
        )
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 25)
        self.assertEqual(
            approved_sellable_stock_quantity(self.product, self.variant),
            5,
        )

    def test_variant_delete_pending_keeps_row_until_approved(self):
        variant_id = self.variant.id
        resp = self.client.delete(
            f'/api/products/variants/{variant_id}/',
            {'reason': 'Discontinue size'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(ProductVariant.objects.filter(pk=variant_id).exists())
        pending = PendingChange.objects.get(
            entity_type='products.ProductVariant',
            action_type=ACTION_PRODUCT_DELETE,
        )
        self._checker_client().post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertFalse(ProductVariant.objects.filter(pk=variant_id).exists())


class MakerCheckerCategoryTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.checker = User.objects.create_user('chk_cat', password='x', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.category = Category.objects.create(name='MC Category', is_active=True)

    def setUp(self):
        super().setUp()
        _enable_maker_checker()
        PendingChange.objects.all().delete()

    def _checker_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_category_deactivate_pending_keeps_active(self):
        resp = self.client.patch(
            f'/api/products/categories/{self.category.id}/',
            {'is_active': False, 'reason': 'Season ended'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.data)
        self.category.refresh_from_db()
        self.assertTrue(self.category.is_active)
        pending = PendingChange.objects.get(action_type=ACTION_CATEGORY_DEACTIVATE)
        self._checker_client().post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_active)

    def test_category_delete_pending_keeps_row_until_approved(self):
        cat_id = self.category.id
        resp = self.client.delete(
            f'/api/products/categories/{cat_id}/',
            {'reason': 'Obsolete category'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(Category.objects.filter(pk=cat_id).exists())
        pending = PendingChange.objects.get(action_type=ACTION_CATEGORY_DELETE)
        self._checker_client().post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertFalse(Category.objects.filter(pk=cat_id).exists())

    def test_category_name_update_applies_immediately(self):
        resp = self.client.patch(
            f'/api/products/categories/{self.category.id}/',
            {'name': 'Renamed MC Category'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Renamed MC Category')
        self.assertFalse(PendingChange.objects.exists())
