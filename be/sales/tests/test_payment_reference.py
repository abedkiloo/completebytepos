"""Payment reference validation for non-cash POS sales."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status

from products.models import Category, Product
from sales.payment_reference import validate_sale_payment_reference
from utils.tests.api_test_base import ManagerAPITestCase


class PaymentReferenceUnitTests(ManagerAPITestCase):
    def test_cash_reference_optional(self):
        self.assertEqual(validate_sale_payment_reference('cash', ''), '')

    def test_mpesa_requires_reference(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            validate_sale_payment_reference('mpesa', '')

    def test_mpesa_strips_reference(self):
        self.assertEqual(
            validate_sale_payment_reference('mpesa', '  QHX123  '),
            'QHX123',
        )


class PaymentReferenceAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Pay Ref Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Pay Ref Item',
            sku='PAY-REF-1',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )

    def test_pos_mpesa_without_reference_rejected(self):
        response = self.client.post(
            '/api/sales/',
            {
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
                'payment_method': 'mpesa',
                'amount_paid': '100.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('payment_reference', response.data)

    def test_pos_mpesa_with_reference_succeeds(self):
        from settings.test_utils import disable_maker_checker

        disable_maker_checker()
        response = self.client.post(
            '/api/sales/',
            {
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
                'payment_method': 'mpesa',
                'amount_paid': '100.00',
                'payment_reference': 'QHX1ABC2DE',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['payment_reference'], 'QHX1ABC2DE')
