"""Customer create/update stores phones with country prefix 254."""

from rest_framework import status

from sales.models import Customer
from settings.models import ModuleSetting, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


class CustomerPhonePrefixAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        ModuleSettings.objects.update_or_create(
            module_name='customers',
            defaults={'description': 'customers', 'is_enabled': True},
        )
        ModuleSetting.objects.update_or_create(
            module='customers',
            key='enable_customer_create',
            defaults={
                'label': 'enable_customer_create',
                'description': '',
                'default_value': True,
                'value': True,
            },
        )

    def test_create_prefixes_local_kenyan_number(self):
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'Jane Doe', 'phone': '0712345678'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['phone'], '254712345678')
        customer = Customer.objects.get(pk=response.data['id'])
        self.assertEqual(customer.phone, '254712345678')

    def test_create_keeps_existing_254_prefix(self):
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'John Doe', 'phone': '+254722000111'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['phone'], '254722000111')

    def test_create_rejects_invalid_phone(self):
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'Bad Phone', 'phone': '123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_create_allows_blank_phone(self):
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'No Phone'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data.get('phone') or '', '')

    def test_create_stores_duka_contact_and_typical_goods(self):
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Wambua Hardware',
                'phone': '0712345678',
                'owner_name': 'John Wambua',
                'contact_person': 'Ann',
                'city': 'Nairobi',
                'address': 'Next to the market',
                'typical_goods': ['Cement 50kg', 'Nails', 'Cement 50kg', ''],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['owner_name'], 'John Wambua')
        self.assertEqual(response.data['contact_person'], 'Ann')
        self.assertEqual(response.data['typical_goods'], ['Cement 50kg', 'Nails'])
        self.assertEqual(response.data['city'], 'Nairobi')
        self.assertEqual(response.data['address'], 'Next to the market')

    def test_typical_goods_rejects_overlong_item(self):
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Long Goods Duka',
                'typical_goods': ['x' * 81],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('typical_goods', response.data)
