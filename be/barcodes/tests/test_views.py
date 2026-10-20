"""Barcode API contract and coverage tests."""

from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status

from products.models import Category, Product
from settings.models import ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


class BarcodeAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ModuleSettings.objects.update_or_create(
            module_name='barcodes',
            defaults={'description': 'barcodes', 'is_enabled': True},
        )
        cat = Category.objects.create(name='General')
        cls.product = Product.objects.create(
            name='Tagged item',
            sku='SKU-BAR-1',
            barcode='1234567890123',
            price=10,
            category=cat,
        )
        cls.product_no_barcode = Product.objects.create(
            name='SKU only',
            sku='SKU-ONLY-2',
            barcode=None,
            price=5,
            category=cat,
        )

    def test_generate_requires_product_or_barcode(self):
        url = reverse('barcode-generate')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', res.data)

    def test_generate_for_unknown_product_returns_404(self):
        url = reverse('barcode-generate')
        res = self.client.get(url, {'product_id': 99999})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_generate_for_product_returns_image_payload(self):
        url = reverse('barcode-generate')
        res = self.client.get(url, {'product_id': self.product.id, 'barcode_format': 'code128'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(res.data['image'].startswith('data:image/png;base64,'))

    def test_generate_by_raw_barcode_and_format_alias(self):
        url = reverse('barcode-generate')
        res = self.client.get(
            url,
            {'barcode': 'HELLO', 'format': 'code128', 'include_text': 'false', 'width': 3, 'height': 120},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['barcode'], 'HELLO')

    def test_generate_ean13_ean8_qrcode_and_unknown_format(self):
        url = reverse('barcode-generate')
        for params in (
            {'barcode': '123456789012', 'barcode_format': 'ean13'},
            {'barcode': '1234567', 'barcode_format': 'ean8'},
            {'barcode': 'qr-content', 'barcode_format': 'qrcode', 'height': 150},
            {'barcode': 'FALLBACK', 'barcode_format': 'unknown'},
        ):
            res = self.client.get(url, params)
            self.assertEqual(res.status_code, status.HTTP_200_OK, msg=params)

    def test_generate_uses_sku_when_barcode_empty(self):
        url = reverse('barcode-generate')
        res = self.client.get(url, {'product_id': self.product_no_barcode.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['barcode'], 'SKU-ONLY-2')

    def test_generate_invalid_ean_returns_400(self):
        url = reverse('barcode-generate')
        res = self.client.get(url, {'barcode': 'ABC', 'barcode_format': 'ean13'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.get(url, {'barcode': '12345', 'barcode_format': 'ean13'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.get(url, {'barcode': '123', 'barcode_format': 'ean8'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('barcodes.views.Product.objects.get')
    def test_generate_product_without_barcode_or_sku(self, mock_get):
        mock_get.return_value = MagicMock(barcode=None, sku='')
        url = reverse('barcode-generate')
        res = self.client.get(url, {'product_id': self.product.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('barcodes.views._generate_barcode')
    def test_generate_unexpected_error_returns_500(self, mock_gen):
        mock_gen.side_effect = RuntimeError('boom')
        url = reverse('barcode-generate')
        res = self.client.get(url, {'barcode': 'X'})
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_get_barcode_image_success_and_errors(self):
        url = reverse('barcode-image')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.client.get(url, {'product_id': 99999})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        res = self.client.get(url, {'barcode': 'IMG123', 'barcode_format': 'qrcode'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'image/png')

        res = self.client.get(url, {'product_id': self.product.id, 'include_text': 'false'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.get(url, {'barcode': 'bad', 'barcode_format': 'ean8'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('barcodes.views._generate_qrcode')
    def test_get_barcode_image_server_error_includes_trace(self, mock_qr):
        mock_qr.side_effect = Exception('fail')
        url = reverse('barcode-image')
        res = self.client.get(url, {'barcode': 'x', 'barcode_format': 'qrcode'})
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('detail', res.data)

    def test_generate_missing_barcodes_all_without_codes(self):
        url = reverse('barcode-generate-missing')
        Product.objects.filter(pk=self.product_no_barcode.pk).update(barcode='')
        res = self.client.post(url, {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['generated'], 1)

    def test_generate_missing_barcodes_specific_ids_and_prefix(self):
        url = reverse('barcode-generate-missing')
        Product.objects.filter(pk=self.product_no_barcode.pk).update(barcode=None)
        res = self.client.post(
            url,
            {'product_ids': [self.product_no_barcode.id], 'prefix': 'PX', 'format': 'code128'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['generated'], 1)
        self.assertTrue(res.data['products'][0]['barcode'].startswith('PX'))

    @patch('uuid.uuid4')
    def test_generate_missing_barcodes_without_sku_uses_uuid(self, mock_uuid):
        mock_uuid.return_value = MagicMock(hex='abcd1234567890abcdef')
        cat = Category.objects.create(name='Gen2')
        bare = Product.objects.create(
            name='Bare',
            sku='BARE-UUID-1',
            barcode=None,
            price=1,
            category=cat,
        )
        Product.objects.filter(pk=bare.pk).update(sku='')
        url = reverse('barcode-generate-missing')
        res = self.client.post(url, {'product_ids': [bare.id], 'prefix': 'U'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['products'][0]['barcode'].startswith('U'))

    def test_generate_missing_barcodes_uniqueness_suffix(self):
        cat = Category.objects.create(name='Collide')
        Product.objects.create(
            name='Occupied',
            sku='OCCUPIED-1',
            barcode='BCCLASH',
            price=1,
            category=cat,
        )
        victim = Product.objects.create(
            name='Victim',
            sku='CLASH',
            barcode=None,
            price=1,
            category=cat,
        )
        url = reverse('barcode-generate-missing')
        res = self.client.post(url, {'product_ids': [victim.id], 'prefix': 'BC'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['products'][0]['barcode'].startswith('BCCLASH'))
        self.assertNotEqual(res.data['products'][0]['barcode'], 'BCCLASH')

    @patch('barcodes.views.Product.save')
    def test_generate_missing_barcodes_collects_errors(self, mock_save):
        mock_save.side_effect = Exception('save failed')
        url = reverse('barcode-generate-missing')
        res = self.client.post(url, {'product_ids': [self.product_no_barcode.id]}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['errors'], 1)
        self.assertIn('error_list', res.data)

    def test_print_labels_pdf_is_branded(self):
        url = reverse('barcode-print-labels')
        res = self.client.post(url, {'product_ids': [self.product.id]}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))

    def test_print_labels_requires_product_ids(self):
        url = reverse('barcode-print-labels')
        res = self.client.post(url, {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_print_labels_options_and_pagination(self):
        url = reverse('barcode-print-labels')
        res = self.client.post(
            url,
            {
                'product_ids': [self.product.id],
                'barcode_format': 'qrcode',
                'include_price': True,
                'include_name': False,
                'quantity': 12,
                'label_width': 4,
                'label_height': 2,
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.content.startswith(b'%PDF'))

    @patch('reportlab.pdfgen.canvas.Canvas')
    def test_print_labels_failure_returns_500(self, mock_canvas):
        mock_canvas.side_effect = Exception('pdf fail')
        url = reverse('barcode-print-labels')
        res = self.client.post(url, {'product_ids': [self.product.id]}, format='json')
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch('barcodes.views.qrcode.QRCode.make')
    def test_qrcode_empty_value_raises_value_error(self, mock_make):
        mock_make.side_effect = ValueError('empty')
        url = reverse('barcode-generate')
        res = self.client.get(url, {'barcode': '   ', 'barcode_format': 'qrcode'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
