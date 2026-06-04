"""Unit of measure registry."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from rest_framework import status

from products.models import Category, Product, UnitOfMeasure
from products.units import create_unit, ensure_builtin_units, validate_unit_code
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


class UnitHelpersTests(ManagerAPITestCase):
    def test_builtin_roll_is_active(self):
        ensure_builtin_units()
        self.assertTrue(UnitOfMeasure.objects.filter(code='roll', is_active=True).exists())
        self.assertEqual(validate_unit_code('roll'), 'roll')

    def test_create_custom_unit(self):
        row = create_unit('Bale', 'Bale unit')
        self.assertEqual(row.code, 'bale')
        self.assertTrue(row.is_active)

    def test_validate_rejects_unknown_unit(self):
        ensure_builtin_units()
        with self.assertRaises(ValidationError):
            validate_unit_code('not-a-real-unit-xyz')


class UnitAPIOptionsTests(ManagerAPITestCase):
    def test_list_options_includes_roll(self):
        ensure_builtin_units()
        response = self.client.get('/api/products/units/', {'format': 'options'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [row['code'] for row in response.data.get('results', response.data)]
        self.assertIn('roll', codes)


class UnitAPICreateTests(SuperAdminAPITestCase):
    def test_super_admin_can_add_unit(self):
        response = self.client.post(
            '/api/products/units/',
            {'code': 'spool', 'label': 'Spool'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UnitOfMeasure.objects.filter(code='spool').exists())

    def test_product_save_uses_new_unit(self):
        self.client.post(
            '/api/products/units/',
            {'code': 'spool', 'label': 'Spool'},
            format='json',
        )
        cat = Category.objects.create(name='U Cat', is_active=True)
        product = Product(
            name='Spool Item',
            sku='SPOOL-1',
            category=cat,
            price=Decimal('10'),
            cost=Decimal('5'),
            unit='spool',
            is_active=True,
        )
        product.full_clean()
        product.save()
        self.assertEqual(product.unit, 'spool')
