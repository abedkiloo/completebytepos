"""Customer search finds every customer — including by phone formatting variants."""

from rest_framework import status

from sales.models import Customer
from utils.tests.api_test_base import SuperAdminAPITestCase


class CustomerSearchTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.jane = Customer.objects.create(
            name='Jane Hardware', phone='+254 712 345 678', is_active=True,
        )
        cls.john = Customer.objects.create(
            name='John Cement Yard', phone='0712987654', is_active=True,
        )
        Customer.objects.create(name='Inactive Shop', phone='0700111222', is_active=False)
        cls.by_owner = Customer.objects.create(
            name='Westlands Kiosk',
            owner_name='Amina Otieno',
            phone='0700555001',
            is_active=True,
        )
        cls.by_contact = Customer.objects.create(
            name='River Road Shop',
            contact_person='Brian Kamau',
            phone='0700555002',
            is_active=True,
        )

    def test_search_by_name_finds_customer(self):
        response = self.client.get('/api/sales/customers/', {'search': 'Hardware', 'is_active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row['id'] for row in response.data['results']]
        self.assertIn(self.jane.id, ids)

    def test_search_by_owner_name(self):
        response = self.client.get(
            '/api/sales/customers/', {'search': 'Amina', 'is_active': 'true'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row['id'] for row in response.data['results']]
        self.assertIn(self.by_owner.id, ids)

    def test_search_by_contact_person(self):
        response = self.client.get(
            '/api/sales/customers/', {'search': 'Brian Kamau', 'is_active': 'true'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row['id'] for row in response.data['results']]
        self.assertIn(self.by_contact.id, ids)

    def test_search_by_local_phone_matches_international_format(self):
        response = self.client.get(
            '/api/sales/customers/', {'search': '0712345678', 'is_active': 'true'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row['id'] for row in response.data['results']]
        self.assertIn(self.jane.id, ids)

    def test_search_by_international_phone_matches_local_format(self):
        response = self.client.get(
            '/api/sales/customers/', {'search': '254712987654', 'is_active': 'true'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row['id'] for row in response.data['results']]
        self.assertIn(self.john.id, ids)

    def test_inactive_customers_are_hidden_when_requested(self):
        response = self.client.get(
            '/api/sales/customers/', {'search': 'Inactive', 'is_active': 'true'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])
