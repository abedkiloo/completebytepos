from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from inventory.models import StockMovement
from inventory.services import StockMovementService
from products.models import Category, Color, Product, ProductVariant, Size


class StockMovementServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inv', password='test')
        self.service = StockMovementService()
        cat = Category.objects.create(name='Test Cat')
        self.product = Product.objects.create(
            name='Test Item',
            sku='INV-TEST-1',
            category=cat,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )

    def test_purchase_stock_increments_quantity(self):
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=5,
            unit_cost=Decimal('5.00'),
            user=self.user,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 15)

    def test_purchase_rejects_non_positive_quantity(self):
        with self.assertRaises(ValidationError):
            self.service.purchase_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=0,
                unit_cost=Decimal('5.00'),
                user=self.user,
            )

    def test_adjustment_negative_below_zero_blocked(self):
        with self.assertRaises(ValidationError):
            self.service.adjust_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=-100,
                notes='over-adjust',
                user=self.user,
            )

    def test_build_queryset_filters_by_product(self):
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=2,
            unit_cost=Decimal('5.00'),
            user=self.user,
        )
        qs = self.service.build_queryset({'product': self.product.id})
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().product_id, self.product.id)

    def test_build_queryset_filters_by_movement_type(self):
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            unit_cost=Decimal('5.00'),
            user=self.user,
        )
        qs = self.service.build_queryset({'movement_type': 'purchase'})
        self.assertTrue(qs.filter(movement_type='purchase').exists())

    def test_get_inventory_report_structure(self):
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=3,
            unit_cost=Decimal('5.00'),
            user=self.user,
        )
        report = self.service.get_inventory_report(product_id=self.product.id)
        self.assertIn('by_movement_type', report)
        self.assertIn('recent_movements', report)
        self.assertGreaterEqual(len(report['recent_movements']), 1)
        self.assertIn('total_products', report)
        self.assertIn('tracked_products', report)
        self.assertGreaterEqual(report['total_movements_this_month'], 1)

    def test_build_queryset_invalid_product_returns_empty(self):
        qs = self.service.build_queryset({'product': 'not-int'})
        self.assertEqual(qs.count(), 0)

    def test_transfer_stock_product_not_found(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='SVC'
        )
        with self.assertRaises(ValidationError):
            self.service.transfer_stock(
                product_id=999999,
                variant_id=None,
                quantity=1,
                from_branch=branch_a,
                to_branch=branch_b,
                user=self.user,
            )

    def test_adjust_stock_positive_quantity(self):
        self.service.adjust_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=3,
            notes='restock',
            user=self.user,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 13)

    def test_purchase_product_not_found(self):
        with self.assertRaises(ValidationError):
            self.service.purchase_stock(
                product_id=999999,
                variant_id=None,
                quantity=1,
                unit_cost=Decimal('5.00'),
                user=self.user,
            )

    def test_adjust_product_not_found(self):
        with self.assertRaises(ValidationError):
            self.service.adjust_stock(
                product_id=999999,
                variant_id=None,
                quantity=1,
                user=self.user,
            )

    def test_build_queryset_branch_filter_when_multi_branch_on(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='BRF'
        )
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            unit_cost=Decimal('5.00'),
            user=self.user,
            branch=branch_a,
        )
        qs = self.service.build_queryset({'branch_id': branch_a.id})
        self.assertEqual(qs.count(), 1)
        other = self.service.build_queryset({'branch_id': branch_b.id})
        self.assertEqual(other.count(), 0)

    def test_transfer_stock_between_branches(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='TRF'
        )
        movements = self.service.transfer_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=2,
            from_branch=branch_a,
            to_branch=branch_b,
            user=self.user,
        )
        self.assertEqual(len(movements), 2)
        outbound, inbound = movements
        self.assertEqual(outbound.quantity, -2)
        self.assertEqual(inbound.quantity, 2)
        paired = self.service.find_paired_transfer_movement(outbound)
        self.assertEqual(paired.id, inbound.id)

    def test_transfer_same_branch_raises(self):
        from utils.tests.api_test_base import ManagerAPITestCase

        tenant, branch, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='SAME', branch_names=('Only',)
        )
        with self.assertRaises(ValidationError):
            self.service.transfer_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=1,
                from_branch=branch,
                to_branch=branch,
                user=self.user,
            )

    def test_undo_transfer_non_transfer_raises(self):
        movement = self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            unit_cost=Decimal('5.00'),
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            self.service.undo_transfer(movement, user=self.user)

    def test_get_inventory_report_scoped_by_product(self):
        report = self.service.get_inventory_report(product_id=self.product.id)
        self.assertEqual(report['tracked_products'], 1)

    def test_transfer_insufficient_stock_raises(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='LOW'
        )
        with self.assertRaises(ValidationError):
            self.service.transfer_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=999,
                from_branch=branch_a,
                to_branch=branch_b,
                user=self.user,
            )

    def test_undo_transfer_reverses_pair(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='UND'
        )
        outbound, inbound = self.service.transfer_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            from_branch=branch_a,
            to_branch=branch_b,
            user=self.user,
        )
        original, reverse, reverse_paired = self.service.undo_transfer(outbound, user=self.user)
        self.assertIn('UNDONE', original.notes)
        self.assertIsNotNone(reverse)
        self.assertIsNotNone(reverse_paired)

    def test_adjust_non_tracked_product_raises(self):
        cat = Category.objects.create(name='Non-track')
        loose = Product.objects.create(
            name='Service item',
            sku='SVC-NT',
            category=cat,
            price=Decimal('1.00'),
            cost=Decimal('0.50'),
            track_stock=False,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            self.service.adjust_stock(
                product_id=loose.id,
                variant_id=None,
                quantity=1,
                user=self.user,
            )

    def test_build_queryset_empty_filters_returns_all(self):
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            unit_cost=Decimal('5.00'),
            user=self.user,
        )
        self.assertGreaterEqual(self.service.build_queryset({}).count(), 1)

    def test_build_queryset_invalid_branch_id_returns_empty(self):
        from settings.test_utils import enable_multi_branch_support

        enable_multi_branch_support()
        qs = self.service.build_queryset({'branch_id': 'x'})
        self.assertEqual(qs.count(), 0)

    def test_transfer_zero_quantity_raises(self):
        from utils.tests.api_test_base import ManagerAPITestCase

        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='ZRO'
        )
        with self.assertRaises(ValidationError):
            self.service.transfer_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=0,
                from_branch=branch_a,
                to_branch=branch_b,
                user=self.user,
            )

    def test_purchase_with_variant_updates_variant_stock(self):
        size = Size.objects.create(name='M', code='M', is_active=True)
        color = Color.objects.create(name='Blue', hex_code='#0000FF', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='INV-VAR-1',
            price=Decimal('12.00'),
            cost=Decimal('6.00'),
            stock_quantity=4,
            is_active=True,
        )
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=variant.id,
            quantity=2,
            unit_cost=Decimal('6.00'),
            user=self.user,
        )
        variant.refresh_from_db()
        self.assertEqual(variant.stock_quantity, 6)

    def test_find_paired_transfer_from_inbound_reference(self):
        inbound = StockMovement.objects.create(
            product=self.product,
            movement_type='transfer',
            quantity=2,
            reference='TRF-PAIR01-IN',
            notes='Transfer in from HQ',
            user=self.user,
        )
        StockMovement.objects.create(
            product=self.product,
            movement_type='transfer',
            quantity=-2,
            reference='TRF-PAIR01-OUT',
            notes='Transfer out',
            user=self.user,
        )
        paired = self.service.find_paired_transfer_movement(inbound)
        self.assertEqual(paired.reference, 'TRF-PAIR01-OUT')

    def test_undo_transfer_already_undone_raises(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='DUP'
        )
        outbound, _ = self.service.transfer_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            from_branch=branch_a,
            to_branch=branch_b,
            user=self.user,
        )
        self.service.undo_transfer(outbound, user=self.user)
        with self.assertRaises(ValidationError):
            self.service.undo_transfer(outbound, user=self.user)

    def test_build_queryset_resolves_branch_from_request(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='BRQ'
        )
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            unit_cost=Decimal('5.00'),
            user=self.user,
            branch=branch_a,
        )
        request = RequestFactory().get('/api/inventory/')
        with patch('inventory.services.get_current_branch', return_value=branch_a):
            qs = self.service.build_queryset({'show_all': 'false'}, request=request)
        self.assertEqual(qs.count(), 1)

    def test_build_queryset_date_to_filter(self):
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            unit_cost=Decimal('5.00'),
            user=self.user,
        )
        now = timezone.now()
        qs = self.service.build_queryset({
            'date_from': (now - timezone.timedelta(hours=1)).isoformat(),
            'date_to': (now + timezone.timedelta(hours=1)).isoformat(),
        })
        self.assertGreaterEqual(qs.count(), 1)

    def test_adjust_invalid_variant_raises(self):
        from products.models import ProductVariant

        size = Size.objects.create(name='S', code='S', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            sku='ADJ-V1',
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            stock_quantity=1,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            self.service.adjust_stock(
                product_id=self.product.id,
                variant_id=variant.id + 5000,
                quantity=1,
                user=self.user,
            )

    def test_purchase_non_tracked_product_raises(self):
        cat = Category.objects.create(name='Digital')
        digital = Product.objects.create(
            name='License',
            sku='LIC-1',
            category=cat,
            price=Decimal('5.00'),
            cost=Decimal('1.00'),
            track_stock=False,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            self.service.purchase_stock(
                product_id=digital.id,
                variant_id=None,
                quantity=1,
                unit_cost=Decimal('1.00'),
                user=self.user,
            )

    def test_transfer_with_variant(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='VAR'
        )
        size = Size.objects.create(name='L', code='L', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            sku='TRF-VAR',
            price=Decimal('15.00'),
            cost=Decimal('7.00'),
            stock_quantity=5,
            is_active=True,
        )
        movements = self.service.transfer_stock(
            product_id=self.product.id,
            variant_id=variant.id,
            quantity=1,
            from_branch=branch_a,
            to_branch=branch_b,
            user=self.user,
        )
        self.assertEqual(len(movements), 2)

    def test_find_paired_transfer_heuristic_match(self):
        now = timezone.now()
        outbound = StockMovement.objects.create(
            product=self.product,
            movement_type='transfer',
            quantity=-1,
            notes='Transfer out to Store B',
            user=self.user,
        )
        StockMovement.objects.create(
            product=self.product,
            movement_type='transfer',
            quantity=1,
            notes='Transfer in from HQ',
            user=self.user,
        )
        outbound.created_at = now
        outbound.save(update_fields=['created_at'])
        paired = self.service.find_paired_transfer_movement(outbound)
        self.assertIsNotNone(paired)

    def test_undo_transfer_without_pair(self):
        lone = StockMovement.objects.create(
            product=self.product,
            movement_type='transfer',
            quantity=-1,
            reference='TRF-LONE-OUT',
            notes='Solo transfer',
            user=self.user,
        )
        original, reverse, reverse_paired = self.service.undo_transfer(lone, user=self.user)
        self.assertIsNone(reverse_paired)
        self.assertIn('UNDONE', original.notes)

    def test_transfer_variant_not_found_raises(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='VNF'
        )
        with self.assertRaises(ValidationError):
            self.service.transfer_stock(
                product_id=self.product.id,
                variant_id=99999,
                quantity=1,
                from_branch=branch_a,
                to_branch=branch_b,
                user=self.user,
            )

    def test_transfer_non_tracked_product_raises(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='NTR'
        )
        cat = Category.objects.create(name='Untracked')
        loose = Product.objects.create(
            name='Gift card',
            sku='GC-1',
            category=cat,
            price=Decimal('10.00'),
            cost=Decimal('5.00'),
            track_stock=False,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            self.service.transfer_stock(
                product_id=loose.id,
                variant_id=None,
                quantity=1,
                from_branch=branch_a,
                to_branch=branch_b,
                user=self.user,
            )

    def test_undo_variant_transfer(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, branch_b = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='UV'
        )
        size = Size.objects.create(name='XL', code='XL', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            sku='UNDO-VAR',
            price=Decimal('20.00'),
            cost=Decimal('10.00'),
            stock_quantity=3,
            is_active=True,
        )
        outbound, _ = self.service.transfer_stock(
            product_id=self.product.id,
            variant_id=variant.id,
            quantity=1,
            from_branch=branch_a,
            to_branch=branch_b,
            user=self.user,
        )
        self.service.undo_transfer(outbound, user=self.user)

    def test_get_inventory_report_with_branch(self):
        from settings.test_utils import enable_multi_branch_support
        from utils.tests.api_test_base import ManagerAPITestCase

        enable_multi_branch_support()
        tenant, branch_a, _ = ManagerAPITestCase.create_tenant_with_branches(
            self.user, code='RPT'
        )
        self.service.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            unit_cost=Decimal('5.00'),
            user=self.user,
            branch=branch_a,
        )
        report = self.service.get_inventory_report(branch=branch_a)
        self.assertGreaterEqual(report['total_movements_this_month'], 1)

    def test_purchase_invalid_variant_raises(self):
        from products.models import ProductVariant

        variant = ProductVariant.objects.create(
            product=self.product,
            sku='VAR-1',
            price=Decimal('12.00'),
            cost=Decimal('6.00'),
            stock_quantity=5,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            self.service.purchase_stock(
                product_id=self.product.id,
                variant_id=variant.id + 9999,
                quantity=1,
                unit_cost=Decimal('5.00'),
                user=self.user,
            )
