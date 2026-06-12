"""API tests for Billing POS holding checkout."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Category, Color, Product, ProductVariant, Size
from sales.models import Sale
from sales.services import SaleService
from settings.models import Branch, Tenant
from settings.test_utils import disable_product_variants, enable_product_variants


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

    def test_checkout_uses_variant_stock_when_variants_disabled(self):
        """When the variants feature is off, stock is drawn from variant rows."""
        disable_product_variants()
        size = Size.objects.create(name='Std', code='STD', is_active=True)
        color = Color.objects.create(name='Default', is_active=True)
        awkward = Product.objects.create(
            name='Sofa variant stock',
            sku='BILL-SOFA-001',
            category=self.product.category,
            mrp=Decimal('100'),
            price=Decimal('80'),
            cost=Decimal('50'),
            stock_quantity=0,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        ProductVariant.objects.create(
            product=awkward,
            size=size,
            color=color,
            sku='BILL-SOFA-001-STD',
            price=Decimal('80'),
            stock_quantity=435,
            is_active=True,
        )
        awkward.refresh_from_db()
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

    def test_save_holding_api_with_variant_id(self):
        enable_product_variants()
        size = Size.objects.create(name='Medium', code='M', is_active=True)
        color = Color.objects.create(name='White', hex_code='#ffffff', is_active=True)
        variant_product = Product.objects.create(
            name='Webbing',
            sku='WEB-V',
            category=self.product.category,
            mrp=Decimal('600'),
            price=Decimal('500'),
            cost=Decimal('200'),
            stock_quantity=10,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        variant_product.available_sizes.add(size)
        variant_product.available_colors.add(color)
        variant = ProductVariant.objects.create(
            product=variant_product,
            size=size,
            color=color,
            sku='WEB-M-W',
            price=Decimal('500'),
            cost=Decimal('200'),
            stock_quantity=3,
            is_active=True,
        )
        response = self.client.post(
            '/api/sales/holding/',
            {
                'holding_id': None,
                'items': [
                    {
                        'product_id': variant_product.id,
                        'variant_id': variant.id,
                        'quantity': 1,
                        'unit_price': '500',
                    }
                ],
                'customer_id': None,
                'tax_amount': 0,
                'discount_amount': 0,
                'branch_id': self.branch.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'holding')
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['variant'], variant.id)

    def test_checkout_variant_decrements_variant_row_stock(self):
        """POS size/color checkout decrements the selected variant row."""
        enable_product_variants()
        size = Size.objects.create(name='Large', code='L', is_active=True)
        color = Color.objects.create(name='Blue', hex_code='#0000ff', is_active=True)
        variant_product = Product.objects.create(
            name='Variant pool item',
            sku='WEB-PARENT',
            category=self.product.category,
            mrp=Decimal('100'),
            price=Decimal('80'),
            cost=Decimal('40'),
            stock_quantity=0,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        variant_product.available_sizes.add(size)
        variant_product.available_colors.add(color)
        variant = ProductVariant.objects.create(
            product=variant_product,
            size=size,
            color=color,
            sku='WEB-PARENT-L-B',
            stock_quantity=20,
            is_active=True,
        )
        variant_product.refresh_from_db()
        holding = self.sale_service.save_holding_sale(
            self.user,
            [
                {
                    'product_id': variant_product.id,
                    'variant_id': variant.id,
                    'quantity': 2,
                    'unit_price': '80.00',
                }
            ],
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
        variant_product.refresh_from_db()
        self.assertEqual(variant_product.stock_quantity, 18)
        variant.refresh_from_db()
        self.assertEqual(variant.stock_quantity, 18)

    def test_save_holding_rejects_product_id_as_variant_id(self):
        enable_product_variants()
        response = self.client.post(
            '/api/sales/holding/',
            {
                'items': [
                    {
                        'product_id': self.product.id,
                        'variant_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '80',
                    }
                ],
                'branch_id': self.branch.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('variant_id', response.data.get('error', '').lower())
