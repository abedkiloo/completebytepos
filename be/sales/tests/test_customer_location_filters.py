"""Customer list filters by Kenya admin location and invalid catalog rows."""

from rest_framework import status

from sales.kenya_admin import (
    DEFAULT_COUNTY,
    DEFAULT_SUB_COUNTY,
    DEFAULT_WARD,
    LOCATION_INVALID_WARD,
    LOCATION_MISSING,
    classify_admin_location,
)
from sales.models import Customer
from utils.tests.api_test_base import SuperAdminAPITestCase


class ClassifyAdminLocationTests(SuperAdminAPITestCase):
    def test_valid_default_triple(self):
        ok, issue = classify_admin_location(
            DEFAULT_COUNTY, DEFAULT_SUB_COUNTY, DEFAULT_WARD
        )
        self.assertTrue(ok)
        self.assertEqual(issue, '')

    def test_missing_and_bad_ward(self):
        ok, issue = classify_admin_location('', 'Starehe', 'Landimawe')
        self.assertFalse(ok)
        self.assertEqual(issue, LOCATION_MISSING)
        ok, issue = classify_admin_location('Nairobi', 'Starehe', 'NotAWard')
        self.assertFalse(ok)
        self.assertEqual(issue, LOCATION_INVALID_WARD)


class CustomerLocationFilterAPITests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        self.valid = Customer.objects.create(
            name='Valid Loc Duka',
            phone='0700000001',
            county=DEFAULT_COUNTY,
            sub_county=DEFAULT_SUB_COUNTY,
            ward=DEFAULT_WARD,
            is_active=True,
        )
        self.blank = Customer.objects.create(
            name='Blank Loc Duka',
            phone='0700000002',
            county='',
            sub_county='',
            ward='',
            is_active=True,
        )
        # Bypass create defaults by updating after save
        Customer.objects.filter(pk=self.blank.pk).update(
            county='', sub_county='', ward='', city=''
        )
        self.blank.refresh_from_db()
        self.bad_ward = Customer.objects.create(
            name='Bad Ward Duka',
            phone='0700000003',
            county='Nairobi',
            sub_county='Starehe',
            ward='FakeWardXYZ',
            is_active=True,
        )
        Customer.objects.filter(pk=self.bad_ward.pk).update(ward='FakeWardXYZ')
        self.bad_ward.refresh_from_db()
        self.mombasa = Customer.objects.create(
            name='Mombasa Duka',
            phone='0700000004',
            county='Mombasa',
            sub_county='',
            ward='',
            is_active=True,
        )
        # Force a valid Mombasa triple via update after resolving from tree
        from sales.kenya_admin import apply_location_defaults

        c, s, w = apply_location_defaults('Mombasa', '', '')
        Customer.objects.filter(pk=self.mombasa.pk).update(
            county=c, sub_county=s, ward=w, city=c
        )
        self.mombasa.refresh_from_db()

    def _ids(self, response):
        rows = response.data.get('results', response.data)
        return {row['id'] for row in rows}

    def test_filter_by_county(self):
        response = self.client.get(
            '/api/sales/customers/',
            {'county': 'Nairobi', 'is_active': 'true', 'page_size': 100},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = self._ids(response)
        self.assertIn(self.valid.id, ids)
        self.assertIn(self.bad_ward.id, ids)
        self.assertNotIn(self.mombasa.id, ids)

    def test_filter_by_county_sub_ward(self):
        response = self.client.get(
            '/api/sales/customers/',
            {
                'county': DEFAULT_COUNTY,
                'sub_county': DEFAULT_SUB_COUNTY,
                'ward': DEFAULT_WARD,
                'is_active': 'true',
                'page_size': 100,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = self._ids(response)
        self.assertIn(self.valid.id, ids)
        self.assertNotIn(self.bad_ward.id, ids)
        self.assertNotIn(self.mombasa.id, ids)

    def test_location_status_invalid(self):
        response = self.client.get(
            '/api/sales/customers/',
            {'location_status': 'invalid', 'is_active': 'true', 'page_size': 100},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = self._ids(response)
        self.assertIn(self.blank.id, ids)
        self.assertIn(self.bad_ward.id, ids)
        self.assertNotIn(self.valid.id, ids)
        self.assertNotIn(self.mombasa.id, ids)
        bad_row = next(
            r for r in response.data.get('results', response.data)
            if r['id'] == self.bad_ward.id
        )
        self.assertFalse(bad_row['location_valid'])
        self.assertEqual(bad_row['location_issue'], LOCATION_INVALID_WARD)

    def test_location_status_valid(self):
        response = self.client.get(
            '/api/sales/customers/',
            {'location_status': 'valid', 'is_active': 'true', 'page_size': 100},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = self._ids(response)
        self.assertIn(self.valid.id, ids)
        self.assertIn(self.mombasa.id, ids)
        self.assertNotIn(self.blank.id, ids)
        self.assertNotIn(self.bad_ward.id, ids)

    def test_unknown_county_returns_empty(self):
        response = self.client.get(
            '/api/sales/customers/',
            {'county': 'Atlantis', 'is_active': 'true'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self._ids(response), set())

    def test_patch_fixes_invalid_location(self):
        response = self.client.patch(
            f'/api/sales/customers/{self.bad_ward.id}/',
            {
                'name': self.bad_ward.name,
                'gender': self.bad_ward.gender or 'female',
                'county': DEFAULT_COUNTY,
                'sub_county': DEFAULT_SUB_COUNTY,
                'ward': DEFAULT_WARD,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['ward'], DEFAULT_WARD)
        follow = self.client.get(
            '/api/sales/customers/',
            {'location_status': 'invalid', 'is_active': 'true', 'page_size': 100},
        )
        self.assertNotIn(self.bad_ward.id, self._ids(follow))
