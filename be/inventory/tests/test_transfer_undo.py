"""Transfer + undo API tests (multi-branch)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from rest_framework import status

from inventory.models import StockMovement
from inventory.services import StockMovementService
from products.models import Category, Product
from settings.test_utils import disable_maker_checker, enable_multi_branch_support
from utils.tests.api_test_base import ManagerAPITestCase


class InventoryTransferServiceTestCase(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        enable_multi_branch_support()
        cls.tenant, cls.branch_a, cls.branch_b = cls.create_tenant_with_branches(
            cls.manager_user, code='TRF'
        )
        cat = Category.objects.create(name='Transfer Cat')
        cls.product = Product.objects.create(
            name='Transfer Widget',
            sku='TRF-SVC-001',
            category=cat,
            price=Decimal('50.00'),
            cost=Decimal('30.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        cls.service = StockMovementService()

    def test_transfer_stock_creates_paired_movements(self):
        movements = self.service.transfer_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=5,
            from_branch=self.branch_a,
            to_branch=self.branch_b,
            user=self.manager_user,
        )
        self.assertEqual(len(movements), 2)
        refs = {m.reference for m in movements}
        self.assertTrue(any(r.endswith('-OUT') for r in refs))
        self.assertTrue(any(r.endswith('-IN') for r in refs))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

    def test_transfer_rejects_insufficient_stock(self):
        with self.assertRaises(ValidationError) as ctx:
            self.service.transfer_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=100,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                user=self.manager_user,
            )
        self.assertIn('Insufficient stock', str(ctx.exception))

    def test_transfer_rejects_same_branch(self):
        with self.assertRaises(ValidationError):
            self.service.transfer_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=1,
                from_branch=self.branch_a,
                to_branch=self.branch_a,
                user=self.manager_user,
            )


class InventoryTransferAPITestCase(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        disable_maker_checker()

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        enable_multi_branch_support()
        cls.tenant, cls.branch_a, cls.branch_b = cls.create_tenant_with_branches(
            cls.manager_user, code='API'
        )
        cat = Category.objects.create(name='API Transfer Cat')
        cls.product = Product.objects.create(
            name='API Transfer Item',
            sku='TRF-API-001',
            category=cat,
            price=Decimal('80.00'),
            cost=Decimal('40.00'),
            stock_quantity=15,
            track_stock=True,
            is_active=True,
        )

    def test_transfer_when_branch_support_disabled_returns_400(self):
        from settings.test_utils import disable_multi_branch_support

        disable_multi_branch_support()
        self.set_session_branch(self.tenant, self.branch_a)
        response = self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 2,
                'to_branch_id': self.branch_b.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        enable_multi_branch_support()

    def test_transfer_success_between_branches(self):
        self.set_session_branch(self.tenant, self.branch_a)
        response = self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 3,
                'to_branch_id': self.branch_b.id,
                'reference': 'TRF-TEST-001',
                'notes': 'Shift stock to store B',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn('movements', response.data)
        self.assertEqual(len(response.data['movements']), 2)

    def test_transfer_same_branch_rejected(self):
        self.set_session_branch(self.tenant, self.branch_a)
        response = self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 1,
                'to_branch_id': self.branch_a.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_invalid_destination_branch(self):
        self.set_session_branch(self.tenant, self.branch_a)
        response = self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 1,
                'to_branch_id': 999999,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_undo_transfer_reverses_movements(self):
        self.set_session_branch(self.tenant, self.branch_a)
        transfer = self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 2,
                'to_branch_id': self.branch_b.id,
            },
            format='json',
        )
        self.assertEqual(transfer.status_code, status.HTTP_201_CREATED)
        outbound = StockMovement.objects.filter(
            product=self.product,
            movement_type='transfer',
            quantity__lt=0,
        ).latest('created_at')

        undo = self.client.post(f'/api/inventory/{outbound.id}/undo/')
        self.assertEqual(undo.status_code, status.HTTP_200_OK, undo.data)
        outbound.refresh_from_db()
        self.assertIn('UNDONE', outbound.notes or '')

    def test_undo_non_transfer_movement_rejected(self):
        self.set_session_branch(self.tenant, self.branch_a)
        purchase = self.client.post(
            '/api/inventory/purchase/',
            {
                'product_id': self.product.id,
                'quantity': 1,
                'unit_cost': '40.00',
            },
            format='json',
        )
        self.assertEqual(purchase.status_code, status.HTTP_201_CREATED)
        movement_id = purchase.data['id']
        undo = self.client.post(f'/api/inventory/{movement_id}/undo/')
        self.assertEqual(undo.status_code, status.HTTP_400_BAD_REQUEST)

    def test_undo_already_undone_transfer_rejected(self):
        self.set_session_branch(self.tenant, self.branch_a)
        self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 1,
                'to_branch_id': self.branch_b.id,
            },
            format='json',
        )
        outbound = StockMovement.objects.filter(
            product=self.product,
            movement_type='transfer',
            quantity__lt=0,
        ).latest('created_at')
        first = self.client.post(f'/api/inventory/{outbound.id}/undo/')
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        second = self.client.post(f'/api/inventory/{outbound.id}/undo/')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_movements_filtered_by_branch(self):
        self.set_session_branch(self.tenant, self.branch_a)
        self.client.post(
            '/api/inventory/transfer/',
            {
                'product_id': self.product.id,
                'quantity': 1,
                'to_branch_id': self.branch_b.id,
            },
            format='json',
        )
        response = self.client.get(
            '/api/inventory/',
            {'branch_id': self.branch_a.id, 'movement_type': 'transfer'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(all(m['movement_type'] == 'transfer' for m in results))
