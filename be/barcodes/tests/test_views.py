"""Barcode API contract tests."""

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile, Role
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from products.models import Product, Category
from settings.models import ModuleSettings


class BarcodeAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('barcode_mgr', password='pass')
        manager_role = Role.objects.get(name=ROLE_MANAGER)
        UserProfile.objects.create(
            user=cls.user,
            role='manager',
            custom_role=manager_role,
            is_active=True,
        )
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

    def setUp(self):
        self.client.force_authenticate(user=self.user)

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
