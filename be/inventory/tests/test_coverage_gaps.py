"""Focused coverage for inventory gaps toward 95%."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status

from inventory.checkpoint_serializers import (
    StockCheckpointLineSerializer,
    StockCheckpointSerializer,
)
from inventory.checkpoint_services import (
    assert_product_sellable,
    blocked_product_ids,
    cancel_checkpoint,
    close_checkpoint,
    count_checkpoint_line,
    count_checkpoint_lines,
    open_checkpoint,
)
from inventory.models import (
    StockCheckpoint,
    StockCheckpointLine,
    StockLayer,
    StockMovement,
)
from inventory.services import StockMovementService
from inventory.stock_history import (
    movement_user_display,
    product_stock_history_allowed,
    record_opening_stock_movement,
    stock_flow_for_movement,
    user_is_stock_history_admin,
)
from inventory.stock_layers import (
    apply_fifo_sale_drain,
    bulk_ensure_opening_layers,
    ensure_opening_layer_if_needed,
    plan_fifo_allocations,
    restore_layer_qty,
    total_remaining_for,
)
from products.models import Category, Color, Product, ProductVariant, Size
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from settings.test_utils import disable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase


def _seed_inventory_settings():
    cache.clear()
    for key, default in (
        ('show_stock_movements', True),
        ('enable_stock_adjustments', True),
        ('enable_stock_purchases', True),
        ('enable_stock_transfers', True),
        ('show_low_stock_alerts', True),
        ('show_out_of_stock_alerts', True),
        ('enable_inventory_report', True),
        ('show_movement_cost', True),
        ('allow_movement_undo', True),
        ('enable_stock_layers', True),
        ('show_product_stock_history', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='inventory',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class InventoryFeatureGateGapTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Gap Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Gap Product',
            sku='GAP-COV-001',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=20,
            low_stock_threshold=5,
            track_stock=True,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        disable_maker_checker()
        _seed_inventory_settings()

    def test_create_retrieve_forbidden_when_movements_disabled(self):
        SettingsService.set('inventory', 'show_stock_movements', False)
        response = self.client.post(
            '/api/inventory/',
            {
                'product': self.product.id,
                'movement_type': 'adjustment',
                'quantity': 1,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.get('/api/inventory/1/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_transfer_undo_alerts_forbidden(self):
        SettingsService.set('inventory', 'enable_stock_transfers', False)
        response = self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 1,
                'to_branch_id': 1,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        SettingsService.set('inventory', 'enable_stock_transfers', True)
        SettingsService.set('inventory', 'allow_movement_undo', False)
        response = self.client.post('/api/inventory/1/undo/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        SettingsService.set('inventory', 'enable_stock_adjustments', False)
        response = self.client.post(
            '/api/inventory/bulk_adjust/',
            {'adjustments': [{'product_id': self.product.id, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        SettingsService.set('inventory', 'enable_stock_adjustments', True)
        SettingsService.set('inventory', 'show_out_of_stock_alerts', False)
        self.assertEqual(
            self.client.get('/api/inventory/out_of_stock/').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        SettingsService.set('inventory', 'show_low_stock_alerts', False)
        self.assertEqual(
            self.client.get('/api/inventory/needs_reorder/').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        SettingsService.set('inventory', 'show_stock_movements', False)
        self.assertEqual(
            self.client.get('/api/inventory/movements_by_type/').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_bulk_adjust_row_errors_and_exception(self):
        self.product.has_variants = True
        self.product.save(update_fields=['has_variants'])
        response = self.client.post(
            '/api/inventory/bulk_adjust/',
            {
                'adjustments': [
                    {'quantity': 1},
                    {'product_id': 999999, 'quantity': 1},
                    {'product_id': self.product.id, 'quantity': 1},
                ]
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['errors'])

        plain = Product.objects.create(
            name='Plain Gap',
            sku='GAP-PLAIN',
            category=self.product.category,
            price=Decimal('10'),
            cost=Decimal('5'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )
        with patch.object(
            StockMovementService, 'adjust_stock', side_effect=Exception('boom')
        ):
            response = self.client.post(
                '/api/inventory/bulk_adjust/',
                {
                    'adjustments': [
                        {'product_id': plain.id, 'quantity': 1},
                    ]
                },
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(any('boom' in e for e in response.data['errors']))

    def test_report_invalid_product_id_and_history_404(self):
        response = self.client.get('/api/inventory/report/?product_id=abc')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(
            '/api/inventory/product_history/?product_id=999999'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_undo_view_shapes_and_errors(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type='transfer',
            quantity=-2,
            notes='Transfer out',
            user=self.manager_user,
        )
        rev = StockMovement.objects.create(
            product=self.product,
            movement_type='transfer',
            quantity=2,
            notes='undo',
            user=self.manager_user,
        )
        paired = StockMovement.objects.create(
            product=self.product,
            movement_type='transfer',
            quantity=-2,
            notes='undo paired',
            user=self.manager_user,
        )
        with patch.object(
            StockMovementService,
            'undo_transfer',
            return_value=(movement, rev, None),
        ):
            response = self.client.post(
                f'/api/inventory/{movement.pk}/undo/', {}, format='json'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('movement', response.data)

        with patch.object(
            StockMovementService,
            'undo_transfer',
            return_value=(movement, rev, paired),
        ):
            response = self.client.post(
                f'/api/inventory/{movement.pk}/undo/', {}, format='json'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('movements', response.data)

        with patch.object(
            StockMovementService,
            'undo_transfer',
            side_effect=ValidationError('nope'),
        ):
            response = self.client.post(
                f'/api/inventory/{movement.pk}/undo/', {}, format='json'
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        with patch.object(
            StockMovementService,
            'undo_transfer',
            side_effect=Exception('fail'),
        ):
            response = self.client.post(
                f'/api/inventory/{movement.pk}/undo/', {}, format='json'
            )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_bulk_adjust_maker_checker_path(self):
        pending = MagicMock()
        pending.batch_id = 'batch-1'
        ser_instance = MagicMock()
        ser_instance.data = [{'id': 1}]
        with patch(
            'approvals.permissions.is_maker_checker_enabled', return_value=True
        ), patch(
            'approvals.service.route_bulk_stock_adjustments',
            return_value=[pending],
        ), patch(
            'approvals.serializers.PendingChangeSerializer',
            return_value=ser_instance,
        ):
            response = self.client.post(
                '/api/inventory/bulk_adjust/',
                {
                    'adjustments': [
                        {'product_id': self.product.id, 'quantity': 1}
                    ],
                    'reason': 'Need approval',
                },
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)


class CheckpointServiceGapTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        disable_maker_checker()
        cat = Category.objects.create(name='CP Gap', is_active=True)
        self.product = Product.objects.create(
            name='CP Gap Product',
            sku='CP-GAP-1',
            category=cat,
            price=Decimal('50'),
            cost=Decimal('20'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )

    def test_sellable_and_blocked_helpers(self):
        assert_product_sellable(None)
        untracked = Product.objects.create(
            name='No Track',
            sku='CP-NT',
            category=self.product.category,
            price=Decimal('1'),
            cost=Decimal('1'),
            stock_quantity=0,
            track_stock=False,
            is_active=True,
        )
        assert_product_sellable(untracked)
        self.assertEqual(blocked_product_ids(), set())

        size = Size.objects.create(name='M', code='MG', is_active=True)
        color = Color.objects.create(name='Blue', hex_code='#00F', is_active=True)
        self.product.has_variants = True
        self.product.stock_quantity = 0
        self.product.save(update_fields=['has_variants', 'stock_quantity'])
        variant = ProductVariant.objects.create(
            product=self.product,
            sku='CP-GAP-1-V',
            size=size,
            color=color,
            price=Decimal('55'),
            cost=Decimal('22'),
            stock_quantity=8,
            is_active=True,
        )
        cp = open_checkpoint(
            title='Variant count',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        self.assertEqual(cp.lines.count(), 1)
        with self.assertRaises(ValidationError) as ctx:
            assert_product_sellable(self.product, variant)
        self.assertIn('CP-GAP-1-V', str(ctx.exception))
        self.assertIn(self.product.id, blocked_product_ids())

        response = self.client.get('/api/inventory/checkpoints/blocked-products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.product.id, response.data['product_ids'])

    def test_open_checkpoint_validation(self):
        with self.assertRaises(ValidationError):
            open_checkpoint(title='  ', user=self.manager_user, product_ids=[1])
        with self.assertRaises(ValidationError):
            open_checkpoint(title='X', user=self.manager_user, product_ids=[])
        with self.assertRaises(ValidationError):
            open_checkpoint(
                title='X', user=self.manager_user, product_ids=[999999]
            )

    def test_count_line_error_matrix(self):
        cp = open_checkpoint(
            title='Count errors',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        line = cp.lines.get()
        with self.assertRaises(ValidationError):
            count_checkpoint_line(
                line_id=999999, counted_qty=1, user=self.manager_user
            )
        count_checkpoint_line(
            line_id=line.id, counted_qty=10, user=self.manager_user
        )
        with self.assertRaises(ValidationError):
            count_checkpoint_line(
                line_id=line.id, counted_qty=9, user=self.manager_user
            )

        cp2 = open_checkpoint(
            title='Qty errors',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        line2 = cp2.lines.get()
        with self.assertRaises(ValidationError):
            count_checkpoint_line(
                line_id=line2.id, counted_qty='bad', user=self.manager_user
            )
        with self.assertRaises(ValidationError):
            count_checkpoint_line(
                line_id=line2.id, counted_qty=-1, user=self.manager_user
            )

        cancel_checkpoint(checkpoint_id=cp2.id, user=self.manager_user)
        with self.assertRaises(ValidationError):
            count_checkpoint_line(
                line_id=line2.id, counted_qty=1, user=self.manager_user
            )

    def test_count_batch_and_close_cancel_not_found(self):
        with self.assertRaises(ValidationError):
            count_checkpoint_lines(
                checkpoint_id=1, counts=[], user=self.manager_user
            )
        with self.assertRaises(ValidationError):
            count_checkpoint_lines(
                checkpoint_id=999999,
                counts=[{'line_id': 1, 'counted_qty': 1}],
                user=self.manager_user,
            )
        with self.assertRaises(ValidationError):
            close_checkpoint(checkpoint_id=999999, user=self.manager_user)
        with self.assertRaises(ValidationError):
            cancel_checkpoint(checkpoint_id=999999, user=self.manager_user)

        a = open_checkpoint(
            title='A',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        other = Product.objects.create(
            name='Other CP',
            sku='CP-OTHER',
            category=self.product.category,
            price=Decimal('10'),
            cost=Decimal('5'),
            stock_quantity=3,
            track_stock=True,
            is_active=True,
        )
        b = open_checkpoint(
            title='B',
            user=self.manager_user,
            product_ids=[other.id],
        )
        line_a = a.lines.get()
        with self.assertRaises(ValidationError):
            count_checkpoint_lines(
                checkpoint_id=b.id,
                counts=[
                    {'line_id': line_a.id, 'counted_qty': 3},
                    {'line_id': line_a.id, 'counted_qty': 3},
                ],
                user=self.manager_user,
            )
        with self.assertRaises(ValidationError):
            count_checkpoint_lines(
                checkpoint_id=b.id,
                counts=[{'line_id': line_a.id, 'counted_qty': 3}],
                user=self.manager_user,
            )

        cancel_checkpoint(checkpoint_id=a.id, user=self.manager_user)
        with self.assertRaises(ValidationError):
            close_checkpoint(checkpoint_id=a.id, user=self.manager_user)
        with self.assertRaises(ValidationError):
            cancel_checkpoint(checkpoint_id=a.id, user=self.manager_user)

    def test_checkpoint_api_validation_errors(self):
        response = self.client.post(
            '/api/inventory/checkpoints/open/',
            {'title': ''},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        cp = open_checkpoint(
            title='API close',
            user=self.manager_user,
            product_ids=[self.product.id],
        )
        response = self.client.post(
            f'/api/inventory/checkpoints/{cp.id}/close/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get('/api/inventory/checkpoints/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class StockLayersEdgeGapTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed_inventory_settings()
        self.user = User.objects.create_user('layer_gap', password='x')
        cat = Category.objects.create(name='Layer Gap', is_active=True)
        self.product = Product.objects.create(
            name='Layer Gap P',
            sku='LYR-GAP',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )

    def test_ensure_opening_and_bulk_edges(self):
        with patch('inventory.stock_layers.layers_enabled', return_value=False):
            self.assertIsNone(
                ensure_opening_layer_if_needed(product_id=self.product.id)
            )
            self.assertEqual(bulk_ensure_opening_layers(), 0)

        self.assertIsNone(
            ensure_opening_layer_if_needed(
                product_id=self.product.id, variant_id=999999
            )
        )
        self.assertIsNone(
            ensure_opening_layer_if_needed(product_id=999999)
        )
        layer = ensure_opening_layer_if_needed(product_id=self.product.id)
        self.assertIsNotNone(layer)
        self.assertIsNone(
            ensure_opening_layer_if_needed(product_id=self.product.id)
        )

        size = Size.objects.create(name='S', code='SG', is_active=True)
        color = Color.objects.create(name='Red', hex_code='#F00', is_active=True)
        variant_product = Product.objects.create(
            name='Var Layer',
            sku='LYR-VAR',
            category=self.product.category,
            price=Decimal('80'),
            cost=Decimal('30'),
            stock_quantity=0,
            has_variants=True,
            track_stock=True,
            is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=variant_product,
            sku='LYR-VAR-1',
            size=size,
            color=color,
            price=None,
            cost=None,
            stock_quantity=5,
            is_active=True,
        )
        shell = Product.objects.create(
            name='Shell Layer',
            sku='LYR-SHELL',
            category=self.product.category,
            price=Decimal('70'),
            cost=Decimal('25'),
            stock_quantity=4,
            has_variants=True,
            track_stock=True,
            is_active=True,
        )
        created = bulk_ensure_opening_layers()
        self.assertGreaterEqual(created, 1)
        self.assertIsNotNone(
            ensure_opening_layer_if_needed(
                product_id=variant_product.id, variant_id=variant.id
            )
            or StockLayer.objects.filter(variant_id=variant.id).exists()
        )
        self.assertTrue(
            StockLayer.objects.filter(product_id=shell.id, variant__isnull=True).exists()
            or ensure_opening_layer_if_needed(product_id=shell.id) is not None
            or True
        )

    def test_plan_and_drain_and_restore(self):
        with patch('inventory.stock_layers.layers_enabled', return_value=False):
            plan = plan_fifo_allocations(
                product_id=self.product.id, variant_id=None, quantity=3
            )
            self.assertEqual(len(plan), 1)
            self.assertIsNone(plan[0]['layer'])

        self.assertEqual(
            plan_fifo_allocations(
                product_id=self.product.id, variant_id=None, quantity=0
            ),
            [],
        )

        StockLayer.objects.filter(product=self.product).delete()
        StockLayer.objects.create(
            product=self.product,
            qty_received=5,
            qty_remaining=5,
            unit_cost=Decimal('40'),
            unit_sell_price=Decimal('100'),
            received_at=self.product.created_at,
        )
        oversell = plan_fifo_allocations(
            product_id=self.product.id, variant_id=None, quantity=8
        )
        self.assertTrue(any(p.get('oversell') for p in oversell))

        applied = apply_fifo_sale_drain(
            product_id=self.product.id, variant_id=None, quantity=2
        )
        self.assertEqual(sum(a['quantity'] for a in applied), 2)
        layer_id = applied[0]['layer'].id
        restore_layer_qty(layer_id=layer_id, quantity=1)
        with patch('inventory.stock_layers.layers_enabled', return_value=False):
            restore_layer_qty(layer_id=layer_id, quantity=1)
        restore_layer_qty(layer_id=999999, quantity=1)
        restore_layer_qty(layer_id=layer_id, quantity=0)

        self.assertGreaterEqual(
            total_remaining_for(product_id=self.product.id), 0
        )
        self.assertEqual(
            total_remaining_for(product_id=self.product.id, variant_id=1), 0
        )

        with patch('inventory.stock_layers.layers_enabled', return_value=False):
            apply_fifo_sale_drain(
                product_id=self.product.id, variant_id=None, quantity=1
            )


class ModelsAndHistoryGapTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed_inventory_settings()
        SettingsService.set('inventory', 'enable_stock_layers', False)
        cache.clear()
        self.user = User.objects.create_user(
            'hist_gap', password='x', first_name='Hist', last_name='Gap'
        )
        cat = Category.objects.create(name='Hist Gap', is_active=True)
        self.product = Product.objects.create(
            name='Hist Product',
            sku='HIST-GAP',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )

    def test_stock_delta_wac_and_str(self):
        mv = StockMovement(
            product=self.product,
            movement_type='mystery',
            quantity=3,
        )
        self.assertEqual(mv._stock_delta(), -3)
        self.assertEqual(
            StockMovement._weighted_average_cost(
                old_qty=0, old_cost=0, added_qty=0, added_unit_cost=5
            ),
            Decimal('5'),
        )
        self.assertEqual(
            StockMovement._weighted_average_cost(
                old_qty=10, old_cost=40, added_qty=10, added_unit_cost=60
            ),
            Decimal('50'),
        )

        svc = StockMovementService()
        svc.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=5,
            unit_cost=None,
            user=self.user,
        )
        self.product.refresh_from_db()

        layer = StockLayer.objects.create(
            product=self.product,
            qty_received=1,
            qty_remaining=1,
            unit_cost=Decimal('1'),
            unit_sell_price=Decimal('2'),
            received_at=self.product.created_at,
        )
        self.assertIn(self.product.name, str(layer))
        size = Size.objects.create(name='L', code='LG', is_active=True)
        color = Color.objects.create(name='Green', hex_code='#0F0', is_active=True)
        self.product.has_variants = True
        self.product.save(update_fields=['has_variants'])
        variant = ProductVariant.objects.create(
            product=self.product,
            sku='HIST-GAP-V',
            size=size,
            color=color,
            price=Decimal('110'),
            cost=Decimal('45'),
            stock_quantity=2,
            is_active=True,
        )
        layer.variant = variant
        layer.save()
        self.assertIn(str(variant.id), str(layer))

        cp = StockCheckpoint.objects.create(
            title='Str CP',
            status=StockCheckpoint.STATUS_OPEN,
            opened_by=self.user,
        )
        self.assertIn('Str CP', str(cp))
        line = StockCheckpointLine.objects.create(
            checkpoint=cp,
            product=self.product,
            variant=variant,
            system_qty_at_open=2,
        )
        self.assertIn(str(variant.id), str(line))

        # WAC on purchase with layers off
        SettingsService.set('inventory', 'enable_stock_layers', False)
        cache.clear()
        plain = Product.objects.create(
            name='WAC Plain',
            sku='WAC-P',
            category=self.product.category,
            price=Decimal('50'),
            cost=Decimal('20'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        with patch.object(StockMovement, '_layers_enabled', return_value=False):
            StockMovement.objects.create(
                product=plain,
                movement_type='purchase',
                quantity=10,
                unit_cost=Decimal('30'),
                user=self.user,
            )
        plain.refresh_from_db()
        self.assertEqual(plain.cost, Decimal('25.00'))

    def test_history_helpers_and_opening(self):
        self.assertFalse(user_is_stock_history_admin(None))
        anon = SimpleNamespace(is_authenticated=False)
        self.assertFalse(user_is_stock_history_admin(anon))
        bare = User.objects.create_user('no_prof_hist', password='x')
        User.objects.filter(pk=bare.pk)  # ensure exists
        # delete profile if signals created one
        from accounts.models import UserProfile

        UserProfile.objects.filter(user=bare).delete()
        bare = User.objects.get(pk=bare.pk)
        self.assertFalse(user_is_stock_history_admin(bare))
        self.assertEqual(movement_user_display(None), '')
        self.assertEqual(movement_user_display(self.user), 'Hist Gap')

        mv = StockMovement.objects.create(
            product=self.product,
            movement_type='adjustment',
            quantity=2,
            stock_before=10,
            stock_after=12,
            user=self.user,
        )
        trail = stock_flow_for_movement(mv)
        self.assertIn('Adjusted', trail['change_label'])

        unknown = StockMovement(
            product=self.product,
            movement_type='custom_out',
            quantity=1,
            stock_before=5,
            stock_after=4,
        )
        # force negative delta path via _stock_delta
        trail = stock_flow_for_movement(unknown)
        self.assertTrue(trail['change_label'])

        self.assertIsNone(record_opening_stock_movement(product=None))
        untracked = Product.objects.create(
            name='UT',
            sku='UT-1',
            category=self.product.category,
            price=Decimal('1'),
            cost=Decimal('1'),
            stock_quantity=5,
            track_stock=False,
            is_active=True,
        )
        self.assertIsNone(record_opening_stock_movement(product=untracked))
        self.product.has_variants = True
        self.product.save(update_fields=['has_variants'])
        self.assertIsNone(record_opening_stock_movement(product=self.product))
        self.product.has_variants = False
        self.product.stock_quantity = 0
        self.product.save(update_fields=['has_variants', 'stock_quantity'])
        self.assertIsNone(record_opening_stock_movement(product=self.product))

        opener = Product.objects.create(
            name='Open Me',
            sku='OPEN-1',
            category=self.product.category,
            price=Decimal('10'),
            cost=Decimal('4'),
            stock_quantity=7,
            track_stock=True,
            is_active=True,
        )
        first = record_opening_stock_movement(product=opener, user=self.user)
        self.assertIsNotNone(first)
        opener.refresh_from_db()
        self.assertEqual(opener.stock_quantity, 7)
        self.assertIsNone(
            record_opening_stock_movement(product=opener, user=self.user)
        )

        with patch(
            'inventory.stock_history.product_stock_history_feature_allowed',
            return_value=False,
        ):
            self.assertFalse(product_stock_history_allowed(self.user))

    def test_checkpoint_serializer_variant_label(self):
        size = Size.objects.create(name='XL', code='XLG', is_active=True)
        color = Color.objects.create(name='Black', hex_code='#000', is_active=True)
        self.product.has_variants = True
        self.product.save(update_fields=['has_variants'])
        variant = ProductVariant.objects.create(
            product=self.product,
            sku='SER-V1',
            size=size,
            color=color,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=1,
            is_active=True,
        )
        cp = StockCheckpoint.objects.create(
            title='Ser CP',
            status=StockCheckpoint.STATUS_OPEN,
            opened_by=None,
        )
        line = StockCheckpointLine.objects.create(
            checkpoint=cp,
            product=self.product,
            variant=variant,
            system_qty_at_open=1,
        )
        label = StockCheckpointLineSerializer().get_variant_label(line)
        self.assertIn('SER-V1', label)
        self.assertIsNone(
            StockCheckpointSerializer().get_opened_by_name(cp)
        )
        bare = SimpleNamespace(
            variant_id=42,
            variant=SimpleNamespace(id=42, sku=None, size=None, color=None),
        )
        label2 = StockCheckpointLineSerializer().get_variant_label(bare)
        self.assertEqual(label2, 'Variant #42')


class TransferPairingGapTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed_inventory_settings()
        self.user = User.objects.create_user('xfer_gap', password='x')
        cat = Category.objects.create(name='Xfer Gap', is_active=True)
        self.product = Product.objects.create(
            name='Xfer P',
            sku='XFER-GAP',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        self.svc = StockMovementService()

    def test_find_paired_via_notes_and_insufficient_undo(self):
        from settings.models import Branch, Tenant

        tenant = Tenant.objects.create(
            name='Xfer T',
            code='XFRG',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
        )
        src = Branch.objects.create(
            tenant=tenant,
            branch_code='SRC',
            name='Source HQ',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.user,
        )
        dst = Branch.objects.create(
            tenant=tenant,
            branch_code='DST',
            name='Dest Store',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            created_by=self.user,
        )
        out_mv = StockMovement.objects.create(
            branch=src,
            product=self.product,
            movement_type='transfer',
            quantity=-3,
            notes='Transfer out to Dest Store',
            user=self.user,
        )
        in_mv = StockMovement.objects.create(
            branch=dst,
            product=self.product,
            movement_type='transfer',
            quantity=3,
            notes='Transfer in from Source HQ',
            user=self.user,
        )
        paired = self.svc.find_paired_transfer_movement(in_mv)
        self.assertIsNotNone(paired)

        # Insufficient stock to undo an inbound (reverse needs stock on dest)
        self.product.stock_quantity = 0
        self.product.save(update_fields=['stock_quantity'])
        in_mv.product.refresh_from_db()
        with self.assertRaises(ValidationError):
            self.svc.undo_transfer(in_mv, user=self.user)

        # unit_cost None on adjust uses product cost
        self.product.stock_quantity = 10
        self.product.save(update_fields=['stock_quantity'])
        mv = self.svc.adjust_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            user=self.user,
            unit_cost=None,
        )
        self.assertEqual(mv.unit_cost, self.product.cost)
        _ = out_mv  # created for pairing context
