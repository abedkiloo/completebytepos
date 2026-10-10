"""Kenya county / sub-county / ward on customers."""

from rest_framework import status

from sales.kenya_admin import (
    DEFAULT_COUNTY,
    DEFAULT_SUB_COUNTY,
    DEFAULT_WARD,
    validate_admin_location,
)
from sales.models import Customer
from utils.tests.api_test_base import SuperAdminAPITestCase


class KenyaAdminValidationTests(SuperAdminAPITestCase):
    def test_defaults_resolve_to_nairobi_starehe_landimawe(self):
        result = validate_admin_location('', '', '', apply_defaults=True)
        self.assertNotIsInstance(result, dict)
        self.assertEqual(result, (DEFAULT_COUNTY, DEFAULT_SUB_COUNTY, DEFAULT_WARD))

    def test_invalid_ward_rejected_without_defaults(self):
        errors = validate_admin_location('Nairobi', 'Starehe', 'Not A Ward', apply_defaults=False)
        self.assertIsInstance(errors, dict)
        self.assertIn('ward', errors)

    def test_county_only_fills_valid_sub_and_ward(self):
        result = validate_admin_location('Mombasa', '', '', apply_defaults=True)
        self.assertNotIsInstance(result, dict)
        county, sub_county, ward = result
        self.assertEqual(county, 'Mombasa')
        self.assertTrue(sub_county)
        self.assertTrue(ward)
        self.assertNotEqual(sub_county, DEFAULT_SUB_COUNTY)

    def test_mismatched_location_repaired_with_defaults(self):
        result = validate_admin_location(
            'Mombasa', 'Starehe', 'Landimawe', apply_defaults=True
        )
        self.assertNotIsInstance(result, dict)
        self.assertEqual(result[0], 'Mombasa')


class CustomerKenyaLocationAPITests(SuperAdminAPITestCase):
    def test_kenya_locations_endpoint(self):
        response = self.client.get('/api/sales/customers/kenya-locations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('counties', response.data)
        self.assertIn('Nairobi', response.data['counties'])
        self.assertEqual(response.data['defaults']['county'], DEFAULT_COUNTY)

    def test_desk_create_gets_default_admin_location(self):
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'Desk Duka', 'customer_type': 'business', 'phone': '0712345678'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['county'], DEFAULT_COUNTY)
        self.assertEqual(response.data['sub_county'], DEFAULT_SUB_COUNTY)
        self.assertEqual(response.data['ward'], DEFAULT_WARD)
        customer = Customer.objects.get(id=response.data['id'])
        self.assertEqual(customer.city, DEFAULT_COUNTY)

    def test_create_with_only_name_still_succeeds(self):
        response = self.client.post(
            '/api/sales/customers/',
            {'name': 'Bare Minimum Duka', 'customer_type': 'business'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['county'], DEFAULT_COUNTY)

    def test_create_with_county_only_succeeds(self):
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'County Only Duka',
                'customer_type': 'business',
                'phone': '0712345680',
                'county': 'Mombasa',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['county'], 'Mombasa')
        self.assertTrue(response.data['sub_county'])
        self.assertTrue(response.data['ward'])

    def test_create_with_explicit_location(self):
        response = self.client.post(
            '/api/sales/customers/',
            {
                'name': 'Coast Duka',
                'customer_type': 'business',
                'phone': '0712345679',
                'county': 'Mombasa',
                'sub_county': 'Mvita',
                'ward': 'Majengo',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['county'], 'Mombasa')
        self.assertEqual(response.data['ward'], 'Majengo')
