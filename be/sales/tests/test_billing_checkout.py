"""API tests for Billing POS holding checkout."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Category, Product
from sales.models import Sale
from sales.services import SaleService
from settings.models import Branch, Tenant
from settings.test_utils import disable_product_variants


class BillingCheckoutAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='billing_admin',
            email='billing@test.com',
            password='admin123',
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        self.tenant = Tenant.objects.create(
            name='Billing Tenant',
            code='BILL',
            owner=self.user,
            created_by=self.user,
        )
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            branch_code='B1',
            name='Main',
            created_by=self.user,
        )
        category = Category.objects.create(name='General', is_active=True)
        self.product = Product.objects.create(
            name='Test Item',
            sku='BILL-001',
            category=category,
            mrp=Decimal('100.00'),
            price=Decimal('80.00'),
            cost=Decimal('50.00'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        self.sale_service = SaleService()

    def test_build_queryset_excludes_holding_by_default(self):
        holding = self.sale_service.save_holding_sale(
            self.user,
            [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '80.00'}],
            branch=self.branch,
        )
        visible = self.sale_service.build_queryset({})
        self.assertFalse(visible.filter(pk=holding.pk).exists())

        with_holding = self.sale_service.build_queryset({'include_holding': True})
        self.assertTrue(with_holding.filter(pk=holding.pk).exists())

    def test_checkout_holding_sale(self):
        holding = self.sale_service.save_holding_sale(
            self.user,
            [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '80.00'}],
            branch=self.branch,
        )
        response = self.client.post(
            f'/api/sales/{holding.id}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        holding.refresh_from_db()
        self.assertEqual(holding.status, 'completed')
        self.assertEqual(Sale.objects.filter(status='holding', pk=holding.pk).count(), 0)

    def test_checkout_uses_parent_stock_when_variants_disabled(self):
        """Legacy products with has_variants=True but qty on parent must checkout."""
        disable_product_variants()
        awkward = Product.objects.create(
            name='Sofa parent stock',
            sku='BILL-SOFA-001',
            category=self.product.category,
            mrp=Decimal('100'),
            price=Decimal('80'),
            cost=Decimal('50'),
            stock_quantity=435,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        holding = self.sale_service.save_holding_sale(
            self.user,
            [{'product_id': awkward.id, 'quantity': 2, 'unit_price': '80.00'}],
            branch=self.branch,
        )
        resp = self.client.post(
            f'/api/sales/{holding.id}/checkout/',
            {
                'payment_method': 'cash',
                'amount_paid': '200.00',
                'allow_partial_payment': False,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        awkward.refresh_from_db()
        self.assertEqual(awkward.stock_quantity, 433)
