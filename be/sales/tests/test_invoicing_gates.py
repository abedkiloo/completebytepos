"""Invoicing feature gates and invoice create/settle payloads."""

from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from products.models import Category, Product
from sales.models import Invoice
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


def _ensure_invoicing(enabled=True, invoice_creation=True, payment_tracking=True):
    cache.clear()
    module, _ = ModuleSettings.objects.update_or_create(
        module_name='invoicing',
        defaults={'description': 'Invoicing', 'is_enabled': enabled},
    )
    if module.is_enabled != enabled:
        module.is_enabled = enabled
        module.save(update_fields=['is_enabled'])
    for key, name, flag in (
        ('invoice_creation', 'Create invoices', invoice_creation),
        ('payment_tracking', 'Record payments', payment_tracking),
        ('invoice_tracking', 'Invoice tracking', True),
    ):
        ModuleFeature.objects.update_or_create(
            module=module,
            feature_key=key,
            defaults={
                'feature_name': name,
                'description': '',
                'is_enabled': flag,
                'display_order': 1,
            },
        )
        row = module.features.filter(feature_key=key).first()
        if row and row.is_enabled != flag:
            row.is_enabled = flag
            row.save(update_fields=['is_enabled'])


class InvoicingGateAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Inv Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Inv Product',
            sku='INV-PRD-001',
            category=cat,
            price=Decimal('50.00'),
            cost=Decimal('30.00'),
            stock_quantity=10,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        _ensure_invoicing()

    def _manual_invoice_payload(self, *, use_product_alias=True):
        item = {
            'quantity': 1,
            'unit_price': '50.00',
            'description': '',
        }
        if use_product_alias:
            item['product'] = self.product.id
        else:
            item['product_id'] = self.product.id
        return {
            'subtotal': '50.00',
            'tax_amount': '0',
            'discount_amount': '0',
            'total': '50.00',
            'items': [item],
        }

    def test_create_manual_invoice_accepts_product_alias(self):
        response = self.client.post(
            '/api/sales/invoices/',
            self._manual_invoice_payload(use_product_alias=True),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(id=response.data['id'])
        self.assertEqual(invoice.status, 'draft')
        self.assertEqual(invoice.items.count(), 1)

    def test_create_manual_invoice_accepts_product_id(self):
        response = self.client.post(
            '/api/sales/invoices/',
            self._manual_invoice_payload(use_product_alias=False),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_forbidden_when_invoice_creation_off(self):
        _ensure_invoicing(invoice_creation=False)
        response = self.client.post(
            '/api/sales/invoices/',
            self._manual_invoice_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_payment_forbidden_when_payment_tracking_off(self):
        create = self.client.post(
            '/api/sales/invoices/',
            self._manual_invoice_payload(),
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        invoice_id = create.data['id']
        send = self.client.post(f'/api/sales/invoices/{invoice_id}/send/')
        self.assertEqual(send.status_code, status.HTTP_200_OK)

        _ensure_invoicing(payment_tracking=False)
        pay = self.client.post(
            '/api/sales/payments/',
            {
                'invoice': invoice_id,
                'amount': '10.00',
                'payment_method': 'cash',
                'payment_date': '2026-05-31',
            },
            format='json',
        )
        self.assertEqual(pay.status_code, status.HTTP_403_FORBIDDEN)

    def test_payment_accepts_invoice_alias_and_settles(self):
        create = self.client.post(
            '/api/sales/invoices/',
            self._manual_invoice_payload(),
            format='json',
        )
        invoice_id = create.data['id']
        self.client.post(f'/api/sales/invoices/{invoice_id}/send/')
        pay = self.client.post(
            '/api/sales/payments/',
            {
                'invoice': invoice_id,
                'amount': '25.00',
                'payment_method': 'cash',
                'payment_date': '2026-05-31',
            },
            format='json',
        )
        self.assertEqual(pay.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(id=invoice_id)
        self.assertEqual(float(invoice.amount_paid), 25.0)
