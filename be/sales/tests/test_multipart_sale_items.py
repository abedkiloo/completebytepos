"""Multipart POS sale ``items`` JSON — unit, API, stress, and security tests.

Regresses the mobile M-Pesa till flow that attaches a receipt screenshot and
sends cart lines as a JSON string. QueryDict wrapping used to make ListField
reject lines with: Expected a dictionary of items but got type "list".
"""

from __future__ import annotations

import json
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.test import SimpleTestCase
from PIL import Image
from rest_framework import status
from rest_framework.exceptions import ValidationError

from products.models import Category, Product
from sales.models import Sale
from sales.multipart_payload import coerce_request_mapping, parse_json_items_field
from sales.serializers import SaleCreateSerializer
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


def _jpeg_bytes(color=(40, 90, 140)) -> bytes:
    buf = BytesIO()
    Image.new('RGB', (48, 48), color=color).save(buf, format='JPEG')
    return buf.getvalue()


class MultipartItemsUnitTests(SimpleTestCase):
    """Pure helpers — no database."""

    def test_coerce_querydict_to_plain_dict(self):
        q = QueryDict(mutable=True)
        q['payment_method'] = 'mpesa'
        q.setlist('tag', ['a', 'b'])
        plain = coerce_request_mapping(q)
        self.assertIsInstance(plain, dict)
        self.assertFalse(hasattr(plain, 'getlist'))
        self.assertEqual(plain['payment_method'], 'mpesa')
        self.assertEqual(plain['tag'], 'b')
        self.assertEqual(coerce_request_mapping(None), {})
        self.assertEqual(coerce_request_mapping({'x': 1}), {'x': 1})

    def test_parse_json_items_from_querydict_string(self):
        lines = [
            {'product_id': 1, 'quantity': 2, 'unit_price': 100},
            {'product_id': 2, 'quantity': 1, 'unit_price': 50},
        ]
        q = QueryDict(mutable=True)
        q['items'] = json.dumps(lines)
        q['payment_method'] = 'mpesa'
        parsed = parse_json_items_field(q)
        self.assertIsInstance(parsed, dict)
        self.assertFalse(hasattr(parsed, 'getlist'))
        self.assertEqual(parsed['items'], lines)
        self.assertEqual(parsed['payment_method'], 'mpesa')

    def test_parse_rejects_invalid_json_and_non_list(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_json_items_field({'items': '{not-json'})
        self.assertIn('items', ctx.exception.detail)
        with self.assertRaises(ValidationError) as ctx2:
            parse_json_items_field({'items': json.dumps({'product_id': 1})})
        self.assertIn('list', str(ctx2.exception.detail).lower())

    def test_defensive_unwrap_double_list(self):
        inner = [{'product_id': 9, 'quantity': 1}]
        out = parse_json_items_field({'items': [inner]})
        self.assertEqual(out['items'], inner)


class MultipartSaleCreateSerializerTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        cat = Category.objects.create(name='MP Items Cat', is_active=True)
        self.product = Product.objects.create(
            name='MP Cement',
            sku='MP-CEM-1',
            category=cat,
            price=Decimal('600.00'),
            cost=Decimal('400.00'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )

    def test_serializer_accepts_querydict_items_json_string(self):
        """Corrected functionality: QueryDict + JSON items string validates as line dicts."""
        lines = [
            {
                'product_id': self.product.id,
                'quantity': 1,
                'unit_price': '600.00',
            }
        ]
        q = QueryDict(mutable=True)
        q['items'] = json.dumps(lines)
        q['sale_type'] = 'pos'
        q['payment_method'] = 'cash'
        q['amount_paid'] = '600.00'
        q['client_channel'] = 'mobile'
        ser = SaleCreateSerializer(data=q)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(len(ser.validated_data['items']), 1)
        self.assertEqual(
            ser.validated_data['items'][0]['product_id'],
            self.product.id,
        )

    def test_legacy_querydict_assign_still_reproduced_without_helper(self):
        """Documents the pre-fix failure mode (list-of-lists via getlist)."""
        q = QueryDict(mutable=True)
        q['items'] = json.dumps(
            [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '600.00'}]
        )
        parsed = json.loads(q.get('items'))
        broken = q.copy()
        broken['items'] = parsed  # wraps as [[...]] for getlist
        self.assertIsInstance(broken.getlist('items')[0], list)
        # Plain-dict path used by the helper must not wrap.
        fixed = parse_json_items_field(q)
        self.assertIsInstance(fixed['items'][0], dict)

    def test_json_body_sale_still_works(self):
        ser = SaleCreateSerializer(
            data={
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '600.00',
                    }
                ],
                'payment_method': 'cash',
                'amount_paid': '600.00',
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)


class MultipartSaleCreateAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        cat = Category.objects.create(name='MP API Cat', is_active=True)
        self.product = Product.objects.create(
            name='MP Till Item',
            sku='MP-TILL-1',
            category=cat,
            price=Decimal('600.00'),
            cost=Decimal('400.00'),
            stock_quantity=80,
            track_stock=True,
            is_active=True,
        )

    def test_mpesa_till_multipart_with_receipt_creates_sale(self):
        items = json.dumps(
            [
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'unit_price': '600.00',
                }
            ]
        )
        receipt = SimpleUploadedFile(
            'mpesa.jpg',
            _jpeg_bytes(),
            content_type='image/jpeg',
        )
        response = self.client.post(
            '/api/sales/',
            {
                'items': items,
                'sale_type': 'pos',
                'payment_method': 'mpesa',
                'amount_paid': '600.00',
                'payment_reference': 'UKRT276RH4',
                'mpesa_destination': 'till',
                'client_channel': 'mobile',
                'payment_receipt_image': receipt,
            },
            format='multipart',
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_201_CREATED),
            response.data,
        )
        self.assertNotIn('Expected a dictionary of items', str(response.data))
        sale_id = response.data.get('id')
        self.assertTrue(sale_id)
        sale = Sale.objects.get(id=sale_id)
        self.assertEqual(sale.payment_method, 'mpesa')
        self.assertEqual(sale.items.count(), 1)
        self.assertTrue(sale.payment_receipt_image)

    def test_multipart_bank_destination_also_works(self):
        items = json.dumps(
            [
                {
                    'product_id': self.product.id,
                    'quantity': 1,
                    'unit_price': '600.00',
                }
            ]
        )
        receipt = SimpleUploadedFile(
            'bank.jpg',
            _jpeg_bytes((10, 10, 10)),
            content_type='image/jpeg',
        )
        response = self.client.post(
            '/api/sales/',
            {
                'items': items,
                'sale_type': 'pos',
                'payment_method': 'mpesa',
                'amount_paid': '600.00',
                'payment_reference': 'BANKCODE01',
                'mpesa_destination': 'bank',
                'client_channel': 'mobile',
                'payment_receipt_image': receipt,
            },
            format='multipart',
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_201_CREATED),
            response.data,
        )

    def test_multipart_invalid_items_json_is_400(self):
        """Security: garbage items must not create a sale or leak internals."""
        receipt = SimpleUploadedFile(
            'bad.jpg',
            _jpeg_bytes(),
            content_type='image/jpeg',
        )
        response = self.client.post(
            '/api/sales/',
            {
                'items': '{broken',
                'payment_method': 'mpesa',
                'amount_paid': '600.00',
                'payment_reference': 'BADCODE001',
                'mpesa_destination': 'till',
                'payment_receipt_image': receipt,
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Sale.objects.filter(payment_reference='BADCODE001').count(), 0)
        self.assertNotIn('Traceback', str(response.data))

    def test_multipart_items_stress_repeated_checkouts(self):
        """Stress: many till+receipt checkouts keep accepting JSON items."""
        created = 0
        for i in range(15):
            receipt = SimpleUploadedFile(
                f'stress-{i}.jpg',
                _jpeg_bytes((200, 50, 50)),
                content_type='image/jpeg',
            )
            response = self.client.post(
                '/api/sales/',
                {
                    'items': json.dumps(
                        [
                            {
                                'product_id': self.product.id,
                                'quantity': 1,
                                'unit_price': '600.00',
                            }
                        ]
                    ),
                    'sale_type': 'pos',
                    'payment_method': 'mpesa',
                    'amount_paid': '600.00',
                    'payment_reference': f'STRESSMP{i:03d}',
                    'mpesa_destination': 'till',
                    'client_channel': 'mobile',
                    'payment_receipt_image': receipt,
                },
                format='multipart',
            )
            self.assertIn(
                response.status_code,
                (status.HTTP_200_OK, status.HTTP_201_CREATED),
                response.data,
            )
            created += 1
        self.assertEqual(created, 15)
        self.assertGreaterEqual(
            Sale.objects.filter(payment_method='mpesa').count(),
            15,
        )


class MultipartSaleCreateSalesPersonaTests(SalesAPITestCase):
    """Sales staff can still post multipart till collections."""

    def setUp(self):
        super().setUp()
        cat = Category.objects.create(name='MP Sales Cat', is_active=True)
        self.product = Product.objects.create(
            name='MP Sales Item',
            sku='MP-SALES-1',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )

    def test_sales_persona_multipart_mpesa(self):
        receipt = SimpleUploadedFile(
            'sales.jpg',
            _jpeg_bytes(),
            content_type='image/jpeg',
        )
        response = self.client.post(
            '/api/sales/',
            {
                'items': json.dumps(
                    [
                        {
                            'product_id': self.product.id,
                            'quantity': 1,
                            'unit_price': '100.00',
                        }
                    ]
                ),
                'sale_type': 'pos',
                'payment_method': 'mpesa',
                'amount_paid': '100.00',
                'payment_reference': 'SALESMP001',
                'mpesa_destination': 'till',
                'client_channel': 'mobile',
                'payment_receipt_image': receipt,
            },
            format='multipart',
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_201_CREATED),
            response.data,
        )
