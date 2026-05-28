"""Unit tests for StockMovementService.undo_transfer."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from inventory.models import StockMovement
from inventory.services import StockMovementService
from products.models import Category, Product
from settings.test_utils import enable_multi_branch_support
from utils.tests.api_test_base import ManagerAPITestCase


class UndoTransferServiceTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        enable_multi_branch_support()
        cls.user = User.objects.create_user(username='undo_svc', password='x')
        cls.tenant, cls.branch_a, cls.branch_b = ManagerAPITestCase.create_tenant_with_branches(
            cls.user, code='UNDO'
        )
        cat = Category.objects.create(name='Undo Cat')
        cls.product = Product.objects.create(
            name='Undo Product',
            sku='UNDO-SVC-1',
            category=cat,
            price=Decimal('20'),
            cost=Decimal('10'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        cls.service = StockMovementService()

    def test_undo_transfer_reverses_paired_movements(self):
        outbound, inbound = self.service.transfer_stock(
            self.product.id, None, 2, self.branch_a, self.branch_b, user=self.user
        )
        _, reverse, reverse_paired = self.service.undo_transfer(outbound, user=self.user)
        outbound.refresh_from_db()
        inbound.refresh_from_db()
        self.assertIn('UNDONE', outbound.notes)
        self.assertIn('UNDONE', inbound.notes)
        self.assertIsNotNone(reverse)
        self.assertIsNotNone(reverse_paired)

    def test_undo_non_transfer_raises(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type='purchase',
            quantity=1,
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            self.service.undo_transfer(movement, user=self.user)

    def test_find_paired_by_reference(self):
        outbound, inbound = self.service.transfer_stock(
            self.product.id, None, 1, self.branch_a, self.branch_b, user=self.user
        )
        paired = self.service.find_paired_transfer_movement(outbound)
        self.assertEqual(paired.id, inbound.id)
