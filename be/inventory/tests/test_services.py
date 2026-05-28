from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.core.exceptions import ValidationError

from inventory.services import StockMovementService
from products.models import Category, Product


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
