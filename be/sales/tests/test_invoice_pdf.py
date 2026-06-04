"""Invoice PDF download API."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from products.models import Category, Product
from sales.models import Invoice, InvoiceItem
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


def _ensure_invoicing():
    cache.clear()
    module, _ = ModuleSettings.objects.update_or_create(
        module_name='invoicing',
        defaults={'description': 'Invoicing', 'is_enabled': True},
    )
    for key, name in (
        ('invoice_creation', 'Create'),
        ('invoice_tracking', 'Track'),
        ('payment_tracking', 'Pay'),
    ):
        ModuleFeature.objects.update_or_create(
            module=module,
            feature_key=key,
            defaults={'feature_name': name, 'description': '', 'is_enabled': True, 'display_order': 1},
        )


class InvoicePdfDownloadTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _ensure_invoicing()
        cat = Category.objects.create(name='PDF Cat', is_active=True)
        cls.product = Product.objects.create(
            name='PDF Product',
            sku='PDF-001',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=5,
            is_active=True,
        )

    def _invoice_with_item(self):
        invoice = Invoice.objects.create(
            customer_name='Test Customer',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            status='draft',
            created_by=self.manager_user,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100.00'),
            subtotal=Decimal('100.00'),
        )
        return invoice

    def test_download_pdf_returns_pdf_bytes(self):
        invoice = self._invoice_with_item()
        response = self.client.get(f'/api/sales/invoices/{invoice.id}/download_pdf/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_download_pdf_empty_items_still_works(self):
        invoice = Invoice.objects.create(
            customer_name='Empty',
            subtotal=Decimal('0'),
            total=Decimal('0'),
            status='draft',
            created_by=self.manager_user,
        )
        response = self.client.get(f'/api/sales/invoices/{invoice.id}/download_pdf/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.startswith(b'%PDF'))
