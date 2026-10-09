"""Unique customer phone + duplicate cleanup helpers."""

from decimal import Decimal

from rest_framework import status

from sales.customer_phones import find_duplicate_phone_groups
from sales.models import Customer
from utils.tests.api_test_base import SuperAdminAPITestCase


class CustomerPhoneUniquenessTests(SuperAdminAPITestCase):
    def test_create_rejects_duplicate_phone(self):
        Customer.objects.create(
            name='First Duka',
            phone='254712345678',
            is_active=True,
        )
        res = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Second Duka',
                'customer_type': 'business',
                'phone': '0712345678',
                'latitude': -1.29,
                'longitude': 36.82,
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
        self.assertIn('phone', res.data)

    def test_create_allows_same_phone_when_other_inactive(self):
        Customer.objects.create(
            name='Old Dup',
            phone='254700111222',
            is_active=False,
        )
        res = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Fresh Duka',
                'customer_type': 'business',
                'phone': '0700111222',
                'latitude': -1.29,
                'longitude': 36.82,
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

    def test_find_duplicate_phone_groups(self):
        keep = Customer.objects.create(
            name='Keep Me',
            phone='0700999888',
            is_active=True,
            wallet_balance=Decimal('0'),
        )
        Customer.objects.create(
            name='Dup Local',
            phone='254700999888',
            is_active=True,
        )
        groups = find_duplicate_phone_groups()
        phones = {g['phone'] for g in groups}
        self.assertIn('254700999888', phones)
        group = next(g for g in groups if g['phone'] == '254700999888')
        self.assertEqual(group['keep_id'], keep.id)
        self.assertEqual(len(group['deactivate_ids']), 1)
