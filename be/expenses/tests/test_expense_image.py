"""Optional expense image upload."""

from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status

from expenses.models import Expense, ExpenseCategory
from utils.tests.api_test_base import ManagerAPITestCase


def _jpeg_bytes(name='receipt.jpg'):
    buf = BytesIO()
    Image.new('RGB', (32, 32), color=(200, 40, 40)).save(buf, format='JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


class ExpenseImageUploadTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.category = ExpenseCategory.objects.create(
            name='Travel Image Cat',
            is_active=True,
        )

    def test_create_without_image(self):
        res = self.client.post(
            '/api/expenses/',
            {
                'category': self.category.id,
                'amount': '25.00',
                'description': 'Fuel without photo',
                'payment_method': 'cash',
                'expense_date': '2026-11-01',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        expense = Expense.objects.get(pk=res.data['id'])
        self.assertFalse(bool(expense.image))
        self.assertIsNone(res.data.get('image_url'))

    def test_create_with_optional_image(self):
        res = self.client.post(
            '/api/expenses/',
            {
                'category': self.category.id,
                'amount': '40.00',
                'description': 'Fuel with photo',
                'payment_method': 'cash',
                'expense_date': '2026-11-02',
                'image': _jpeg_bytes(),
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        expense = Expense.objects.get(pk=res.data['id'])
        self.assertTrue(bool(expense.image))
        self.assertTrue(res.data.get('image_url'))

    def test_list_includes_image_url(self):
        expense = Expense.objects.create(
            category=self.category,
            amount=Decimal('10.00'),
            description='Listed with image',
            payment_method='cash',
            expense_date='2026-11-03',
            created_by=self.manager_user,
        )
        expense.image.save('list.jpg', _jpeg_bytes('list.jpg'), save=True)
        res = self.client.get('/api/expenses/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rows = res.data.get('results', res.data)
        match = next(r for r in rows if r['id'] == expense.id)
        self.assertTrue(match.get('image_url'))
