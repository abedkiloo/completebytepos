"""Supplier API tests."""

from decimal import Decimal

from rest_framework import status

from settings.models import ModuleSettings
from suppliers.models import Supplier
from suppliers.tests.test_module_settings_phase3 import _seed_supplier_settings
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class SupplierViewsTestCase(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_supplier_settings()

    def test_create_list_and_retrieve_supplier(self):
        create = self.client.post(
            '/api/suppliers/suppliers/',
            {
                'name': 'Fresh Farms Ltd',
                'supplier_type': 'distributor',
                'email': 'orders@fresh.test',
                'phone': '0711222333',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        supplier_id = create.data['id']

        detail = self.client.get(f'/api/suppliers/suppliers/{supplier_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['name'], 'Fresh Farms Ltd')

        listing = self.client.get('/api/suppliers/suppliers/?search=Fresh')
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in listing.data.get('results', listing.data)]
        self.assertIn('Fresh Farms Ltd', names)

    def test_statistics_endpoint(self):
        Supplier.objects.create(
            name='Stats Supplier',
            supplier_type='business',
            is_active=True,
            is_preferred=True,
            account_balance=Decimal('1000.00'),
            created_by=self.manager_user,
        )
        response = self.client.get('/api/suppliers/suppliers/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['total_suppliers'], 1)

    def test_update_supplier(self):
        supplier = Supplier.objects.create(
            name='Old Name',
            supplier_type='business',
            created_by=self.manager_user,
        )
        response = self.client.patch(
            f'/api/suppliers/suppliers/{supplier.id}/',
            {'phone': '0700111222'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        supplier.refresh_from_db()
        self.assertEqual(supplier.phone, '0700111222')


class SupplierPermissionsTestCase(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ModuleSettings.objects.update_or_create(
            module_name='suppliers',
            defaults={'description': 'suppliers', 'is_enabled': True},
        )

    def test_sales_cannot_create_supplier(self):
        response = self.client.post(
            '/api/suppliers/suppliers/',
            {'name': 'Blocked', 'supplier_type': 'business'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_disabled_module_returns_empty_list(self):
        ModuleSettings.objects.filter(module_name='suppliers').update(is_enabled=False)
        response = self.client.get('/api/suppliers/suppliers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('results', response.data), [])
