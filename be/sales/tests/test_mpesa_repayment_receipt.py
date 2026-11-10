"""M-Pesa debt repayment requires a receipt screenshot; past dates are marked."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework import status

from sales.models import Customer, CustomerWalletTransaction
from utils.tests.api_test_base import ManagerAPITestCase


def _jpeg(name='mpesa_receipt.jpg'):
    buf = BytesIO()
    Image.new('RGB', (48, 48), color=(20, 160, 80)).save(buf, format='JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


@patch(
    'sales.customer_module_settings.customers_collection_payer_details_enabled',
    return_value=False,
)
class MpesaRepaymentReceiptTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Receipt Debtor',
            phone='0700111000',
            wallet_balance=Decimal('-200.00'),
        )

    def _url(self):
        return f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/'

    def test_mpesa_without_receipt_rejected(self, _mock):
        res = self.client.post(
            self._url(),
            {
                'amount': '50.00',
                'payment_method': 'mpesa',
                'reference': 'QHX7K2L9M1',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('receipt_image', res.data)

    def test_mpesa_with_receipt_and_past_date(self, _mock):
        past = timezone.localdate() - timedelta(days=2)
        res = self.client.post(
            self._url(),
            {
                'amount': '75.00',
                'payment_method': 'mpesa',
                'reference': 'QHX7K2L9M1',
                'payment_date': past.isoformat(),
                'receipt_image': _jpeg(),
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        txn = CustomerWalletTransaction.objects.get(
            customer=self.customer,
            source_type='debt_settlement',
        )
        self.assertTrue(bool(txn.receipt_image))
        self.assertIsNotNone(txn.occurred_at)
        self.assertEqual(timezone.localtime(txn.occurred_at).date(), past)
        self.assertTrue(res.data['transaction'].get('receipt_image_url'))
        self.assertTrue(res.data['transaction'].get('is_backdated'))

    def test_cash_still_works_without_receipt(self, _mock):
        res = self.client.post(
            self._url(),
            {
                'amount': '25.00',
                'payment_method': 'cash',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        txn = CustomerWalletTransaction.objects.get(
            customer=self.customer,
            source_type='debt_settlement',
        )
        self.assertFalse(bool(txn.receipt_image))
        self.assertFalse(res.data['transaction'].get('is_backdated'))

    def test_future_payment_date_rejected(self, _mock):
        future = timezone.localdate() + timedelta(days=1)
        res = self.client.post(
            self._url(),
            {
                'amount': '10.00',
                'payment_method': 'cash',
                'payment_date': future.isoformat(),
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('payment_date', res.data)
