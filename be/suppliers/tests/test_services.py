"""Supplier service unit tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from suppliers.models import Supplier
from suppliers.services import SupplierService


class SupplierServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sup_svc', password='x')
        self.service = SupplierService()
        self.supplier = Supplier.objects.create(
            name='Acme Wholesale',
            supplier_type='wholesaler',
            email='buy@acme.test',
            phone='0700000001',
            created_by=self.user,
        )

    def test_build_queryset_search_by_name(self):
        qs = self.service.build_queryset({'search': 'Acme'})
        self.assertEqual(qs.count(), 1)

    def test_build_queryset_active_filter(self):
        Supplier.objects.create(
            name='Inactive Co',
            is_active=False,
            created_by=self.user,
        )
        qs = self.service.build_queryset({'is_active': 'false'})
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().name, 'Inactive Co')

    def test_search_suppliers_returns_active_only(self):
        Supplier.objects.create(
            name='Hidden Vendor',
            is_active=False,
            created_by=self.user,
        )
        results = self.service.search_suppliers('Vendor')
        self.assertEqual(results, [])

    def test_update_account_balance_credit_and_debit(self):
        updated = self.service.update_account_balance(
            self.supplier,
            Decimal('500.00'),
            transaction_type='credit',
        )
        self.assertEqual(updated.account_balance, Decimal('500.00'))
        paid = self.service.update_account_balance(
            updated,
            Decimal('200.00'),
            transaction_type='debit',
        )
        self.assertEqual(paid.account_balance, Decimal('300.00'))

    def test_update_account_balance_invalid_type_raises(self):
        with self.assertRaises(ValidationError):
            self.service.update_account_balance(
                self.supplier,
                Decimal('10.00'),
                transaction_type='invalid',
            )

    def test_get_supplier_statistics(self):
        stats = self.service.get_supplier_statistics(self.supplier.id)
        self.assertEqual(stats['supplier_name'], 'Acme Wholesale')
        self.assertIn('product_count', stats)

    def test_get_all_supplier_statistics(self):
        stats = self.service.get_all_supplier_statistics()
        self.assertGreaterEqual(stats['total_suppliers'], 1)
        self.assertIn('by_type', stats)
