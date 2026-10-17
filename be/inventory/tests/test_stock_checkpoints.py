"""Stock checkpoints — sell block, count, inventory journal, close baseline."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounting.models import JournalEntry
from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from inventory.checkpoint_services import (
    assert_product_sellable,
    cancel_checkpoint,
    close_checkpoint,
    count_checkpoint_line,
    latest_closed_checkpoint,
    open_checkpoint,
)
from inventory.models import StockCheckpoint, StockMovement
from products.models import Category, Product
from sales.services import SaleService
from utils.tests.api_test_base import ManagerAPITestCase


class StockCheckpointServiceTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles()
        cat = Category.objects.create(name='CP Cat', is_active=True)
        self.product = Product.objects.create(
            name='Checkpoint Widget',
            sku='CP-W1',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )

    def test_open_blocks_sale_until_counted(self):
        cp = open_checkpoint(
            title='April count',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        self.assertEqual(cp.status, StockCheckpoint.STATUS_OPEN)
        self.assertEqual(cp.lines.count(), 1)
        with self.assertRaises(ValidationError) as ctx:
            assert_product_sellable(self.product)
        self.assertIn('Stock checkpoint open', str(ctx.exception))

        line = cp.lines.get()
        count_checkpoint_line(line_id=line.id, counted_qty=8, user=self.manager_user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)
        assert_product_sellable(self.product)  # no raise

    def test_count_posts_inventory_journal(self):
        from inventory.checkpoint_services import _ensure_inventory_accounts

        inv, _var = _ensure_inventory_accounts()
        before_inv = inv.current_balance

        cp = open_checkpoint(
            title='Journal count',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        line = cp.lines.get()
        # 10 → 12: +2 × 40 = 80 debit inventory
        count_checkpoint_line(line_id=line.id, counted_qty=12, user=self.manager_user)
        inv.refresh_from_db()
        self.assertEqual(inv.current_balance, before_inv + Decimal('80.00'))
        self.assertTrue(
            JournalEntry.objects.filter(
                reference_type='stock_checkpoint',
                reference_id=cp.id,
            ).exists()
        )
        self.assertTrue(
            StockMovement.objects.filter(
                product=self.product,
                movement_type='adjustment',
                reference=f'CHECKPOINT-{cp.id}',
            ).exists()
        )

    def test_close_requires_all_counted_and_sets_baseline(self):
        cp = open_checkpoint(
            title='Close me',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        with self.assertRaises(ValidationError):
            close_checkpoint(checkpoint_id=cp.id, user=self.manager_user)

        line = cp.lines.get()
        count_checkpoint_line(line_id=line.id, counted_qty=10, user=self.manager_user)
        closed = close_checkpoint(checkpoint_id=cp.id, user=self.manager_user)
        self.assertEqual(closed.status, StockCheckpoint.STATUS_CLOSED)
        self.assertIsNotNone(closed.closed_at)
        latest = latest_closed_checkpoint()
        self.assertEqual(latest.id, closed.id)

    def test_cancel_lifts_block_without_stock_change(self):
        cp = open_checkpoint(
            title='Cancel me',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        cancel_checkpoint(checkpoint_id=cp.id, user=self.manager_user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        assert_product_sellable(self.product)

    def test_validate_sale_items_blocks_pending_sku(self):
        open_checkpoint(
            title='POS block',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        with self.assertRaises(ValidationError) as ctx:
            SaleService().validate_sale_items(
                [{'product_id': self.product.id, 'quantity': 1}],
                check_stock=True,
                user=self.manager_user,
            )
        self.assertIn('Stock checkpoint open', str(ctx.exception))

    def test_open_without_block_sales_allows_selling(self):
        cp = open_checkpoint(
            title='Soft count',
            user=self.manager_user,
            product_ids=[self.product.id],
            block_sales=False,
        )
        self.assertFalse(cp.block_sales)
        assert_product_sellable(self.product)
        SaleService().validate_sale_items(
            [{'product_id': self.product.id, 'quantity': 1}],
            check_stock=True,
            user=self.manager_user,
        )

    def test_module_setting_default_controls_block_sales(self):
        from settings.settings_service import SettingsService

        SettingsService.set('inventory', 'block_sales_during_checkpoint', False)
        cp = open_checkpoint(
            title='Default soft',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        self.assertFalse(cp.block_sales)
        assert_product_sellable(self.product)

        SettingsService.set('inventory', 'block_sales_during_checkpoint', True)
        cp2 = open_checkpoint(
            title='Default hard',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        self.assertTrue(cp2.block_sales)
        with self.assertRaises(ValidationError):
            assert_product_sellable(self.product)


class StockCheckpointAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles()
        # Manager role should include inventory.manage via sync
        from accounts.models import Permission

        manage = Permission.objects.filter(module='inventory', action='manage').first()
        if manage:
            self.manager_role.permissions.add(manage)
        cat = Category.objects.create(name='API Cat', is_active=True)
        self.product = Product.objects.create(
            name='API Widget',
            sku='API-W1',
            category=cat,
            price=Decimal('50'),
            cost=Decimal('20'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )

    def test_open_count_close_api(self):
        open_res = self.client.post(
            '/api/inventory/checkpoints/open/',
            {'title': 'API count', 'product_ids': [self.product.id]},
            format='json',
        )
        self.assertEqual(open_res.status_code, status.HTTP_201_CREATED, open_res.data)
        cp_id = open_res.data['id']
        line_id = open_res.data['lines'][0]['id']

        count_res = self.client.post(
            f'/api/inventory/checkpoints/{cp_id}/lines/{line_id}/count/',
            {'counted_qty': 4},
            format='json',
        )
        self.assertEqual(count_res.status_code, status.HTTP_200_OK, count_res.data)
        self.assertEqual(count_res.data['status'], 'counted')

        close_res = self.client.post(f'/api/inventory/checkpoints/{cp_id}/close/')
        self.assertEqual(close_res.status_code, status.HTTP_200_OK, close_res.data)
        self.assertEqual(close_res.data['status'], 'closed')

        baselines = self.client.get('/api/inventory/checkpoints/baselines/')
        self.assertEqual(baselines.status_code, status.HTTP_200_OK)
        self.assertEqual(baselines.data['latest_closed_id'], cp_id)

    def test_sales_person_cannot_open_checkpoint(self):
        sales_user = User.objects.create_user(username='cp_sales', password='sales123')
        UserProfile.objects.create(
            user=sales_user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        token = RefreshToken.for_user(sales_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        res = self.client.post(
            '/api/inventory/checkpoints/open/',
            {'title': 'Nope', 'include_all_tracked': True},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
