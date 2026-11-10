"""Unit + API coverage for collection payer name/phone and till vs bank."""

from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from products.models import Category, Product
from sales.collection_payer import (
    mpesa_destination_label,
    normalize_mpesa_destination,
    normalize_payer_name,
    normalize_payer_phone,
    validate_collection_payer_fields,
)
from sales.models import Customer, CustomerWalletTransaction, Sale, SaleItem
from sales.payments_trail import list_payments_trail
from sales.services import CustomerService
from utils.tests.api_test_base import ManagerAPITestCase


class CollectionPayerUnitTests(TestCase):
    def test_normalize_helpers(self):
        self.assertEqual(normalize_payer_name('  Ann  '), 'Ann')
        self.assertEqual(normalize_payer_phone('+254 712-345-678'), '+254712345678')
        self.assertEqual(normalize_payer_phone('0712 345 678'), '0712345678')
        self.assertEqual(mpesa_destination_label('till'), 'Till')
        self.assertEqual(mpesa_destination_label('bank'), 'Bank')
        self.assertEqual(mpesa_destination_label(''), '')

    def test_normalize_destination_clears_for_cash(self):
        self.assertEqual(
            normalize_mpesa_destination('till', payment_method='cash'),
            '',
        )

    def test_normalize_destination_rejects_unknown(self):
        with self.assertRaises(ValidationError):
            normalize_mpesa_destination('paypal', payment_method='mpesa')

    def test_validate_requires_payer_and_destination(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_collection_payer_fields(
                payment_method='mpesa',
                reference='QHX7K2L9M1',
                require_payer=True,
                require_mpesa_destination_for_code=True,
            )
        errors = ctx.exception.message_dict
        self.assertIn('payer_name', errors)
        self.assertIn('payer_phone', errors)
        self.assertIn('mpesa_destination', errors)

    def test_validate_accepts_complete_payload(self):
        result = validate_collection_payer_fields(
            payment_method='mpesa',
            reference='QHX7K2L9M1',
            payer_name='Ann Payer',
            payer_phone='0712345678',
            mpesa_destination='bank',
        )
        self.assertEqual(result['payer_name'], 'Ann Payer')
        self.assertEqual(result['payer_phone'], '0712345678')
        self.assertEqual(result['mpesa_destination'], 'bank')

    def test_validate_rejects_short_phone(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_collection_payer_fields(
                payment_method='cash',
                payer_name='Ann',
                payer_phone='12345',
                require_payer=True,
                require_mpesa_destination_for_code=False,
            )
        self.assertIn('payer_phone', ctx.exception.message_dict)

    @patch('sales.collection_payer.normalize_mpesa_destination')
    def test_validate_merges_plain_destination_error(self, mock_norm):
        mock_norm.side_effect = ValidationError('bad destination')
        with self.assertRaises(ValidationError) as ctx:
            validate_collection_payer_fields(
                payment_method='mpesa',
                reference='QHX7K2L9M1',
                payer_name='Ann',
                payer_phone='0712345678',
                mpesa_destination='till',
                require_payer=True,
                require_mpesa_destination_for_code=True,
            )
        self.assertIn('mpesa_destination', ctx.exception.message_dict)

    @patch('sales.collection_payer.normalize_mpesa_destination')
    def test_validate_merges_dict_destination_error(self, mock_norm):
        mock_norm.side_effect = ValidationError(
            {'mpesa_destination': 'Choose till or bank.'}
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_collection_payer_fields(
                payment_method='mpesa',
                reference='QHX7K2L9M1',
                payer_name='Ann',
                payer_phone='0712345678',
                mpesa_destination='x',
                require_payer=True,
                require_mpesa_destination_for_code=False,
            )
        self.assertEqual(
            ctx.exception.message_dict['mpesa_destination'],
            ['Choose till or bank.'],
        )


class CollectionPayerAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Payer Customer',
            phone='0700111222',
            wallet_balance=Decimal('-300.00'),
            is_active=True,
        )
        category = Category.objects.create(name='Payer Cat', is_active=True)
        product = Product.objects.create(
            name='Payer Item',
            sku='PAYER-1',
            category=category,
            price=Decimal('300'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='SALE-PAYER-1',
            status='completed',
            sale_type='pos',
            customer=self.customer,
            subtotal=Decimal('300.00'),
            total=Decimal('300.00'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            cashier=self.manager_user,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=self.sale,
            product=product,
            quantity=1,
            unit_price=Decimal('300'),
            subtotal=Decimal('300'),
        )
        CustomerWalletTransaction.objects.create(
            customer=self.customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('300.00'),
            balance_after=Decimal('-300.00'),
            sale=self.sale,
            created_by=self.manager_user,
        )

    @patch(
        'sales.customer_module_settings.customers_collection_payer_details_enabled',
        return_value=True,
    )
    def test_receive_wallet_payment_requires_payer_when_feature_on(self, _mock):
        res = self.client.post(
            f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
            {
                'amount': '100.00',
                'payment_method': 'mpesa',
                'reference': 'QHX7K2L9M1',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)

    @patch(
        'sales.customer_module_settings.customers_collection_payer_details_enabled',
        return_value=True,
    )
    def test_receive_wallet_payment_stores_payer_and_destination(self, _mock):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buf = BytesIO()
        Image.new('RGB', (24, 24), color=(30, 140, 60)).save(buf, format='JPEG')
        receipt = SimpleUploadedFile(
            'payer_receipt.jpg', buf.getvalue(), content_type='image/jpeg'
        )
        res = self.client.post(
            f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
            {
                'amount': '100.00',
                'payment_method': 'mpesa',
                'reference': 'QHX7K2L9M1',
                'payer_name': 'Mary Payer',
                'payer_phone': '0712999888',
                'mpesa_destination': 'till',
                'receipt_image': receipt,
            },
            format='multipart',
        )
        self.assertIn(
            res.status_code,
            (status.HTTP_200_OK, status.HTTP_201_CREATED),
            res.data,
        )
        txn = CustomerWalletTransaction.objects.filter(
            customer=self.customer,
            source_type='debt_settlement',
            reference='QHX7K2L9M1',
        ).latest('id')
        self.assertEqual(txn.payer_name, 'Mary Payer')
        self.assertEqual(txn.payer_phone, '0712999888')
        self.assertEqual(txn.mpesa_destination, 'till')
        self.assertEqual(res.data['transaction']['mpesa_destination'], 'till')

    def test_payments_trail_filters_by_till_and_searches_payer(self):
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('50.00'),
            payment_method='mpesa',
            reference='QHXTILL001',
            user=self.manager_user,
            payer_name='Till Person',
            payer_phone='0700111000',
            mpesa_destination='till',
        )
        CustomerService().record_wallet_payment(
            self.customer,
            Decimal('40.00'),
            payment_method='mpesa',
            reference='QHXBANK001',
            user=self.manager_user,
            payer_name='Bank Person',
            payer_phone='0700222000',
            mpesa_destination='bank',
        )
        today = timezone.localdate().isoformat()
        till_rows = list_payments_trail(
            kind='debt_settlement',
            date_from=today,
            date_to=today,
            mpesa_destination='till',
            user=self.manager_user,
        )
        self.assertEqual(till_rows['count'], 1)
        self.assertEqual(till_rows['results'][0]['mpesa_destination'], 'till')
        self.assertEqual(till_rows['results'][0]['payer_name'], 'Till Person')

        search_rows = list_payments_trail(
            kind='debt_settlement',
            date_from=today,
            date_to=today,
            search='Bank Person',
            user=self.manager_user,
        )
        self.assertEqual(search_rows['count'], 1)
        self.assertEqual(search_rows['results'][0]['mpesa_destination'], 'bank')

        api = self.client.get(
            '/api/sales/customers/payments-trail/',
            {
                'kind': 'debt_settlement',
                'date_from': today,
                'date_to': today,
                'mpesa_destination': 'bank',
            },
        )
        self.assertEqual(api.status_code, status.HTTP_200_OK, api.data)
        self.assertEqual(api.data['count'], 1)
        self.assertEqual(api.data['results'][0]['mpesa_destination'], 'bank')
