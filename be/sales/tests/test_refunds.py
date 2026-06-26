"""TDD: sale refunds — stock return, audit trail, immutability of original sale."""

from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AuditLog, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from inventory.models import StockMovement
from products.models import Category, Product
from sales.models import Sale, SaleItem, SaleRefund
from sales.refunds import SaleRefundService
from sales.services import SaleService
from settings.models import Branch, Tenant
from settings.test_utils import disable_maker_checker, enable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


class SaleRefundServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('refund_svc', password='x')
        cls.cat = Category.objects.create(name='RefCat', is_active=True)
        cls.product = Product.objects.create(
            name='Refundable',
            sku='REF-1',
            category=cls.cat,
            price=Decimal('50'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-REF-100',
            status='completed',
            subtotal=Decimal('100'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100'),
            payment_method='cash',
            amount_paid=Decimal('100'),
            cashier=cls.user,
        )
        cls.line = SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('50'),
            subtotal=Decimal('100'),
        )

    def setUp(self):
        self.service = SaleRefundService()

    def test_full_refund_restores_stock_and_marks_sale(self):
        refund = self.service.create_refund(
            self.sale,
            reason='Customer returned goods',
            user=self.user,
            full=True,
        )
        self.assertEqual(refund.amount, Decimal('100'))
        self.assertEqual(refund.refund_type, 'full')
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 12)
        self.assertTrue(
            StockMovement.objects.filter(
                movement_type='return',
                reference=refund.refund_number,
            ).exists()
        )

    def test_partial_refund_one_unit(self):
        refund = self.service.create_refund(
            self.sale,
            reason='One item damaged',
            user=self.user,
            items=[{'sale_item_id': self.line.id, 'quantity': 1}],
        )
        self.assertEqual(refund.amount, Decimal('50'))
        self.assertEqual(refund.refund_type, 'partial')
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'partial')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 11)

    def test_cannot_refund_more_than_remaining_qty(self):
        self.service.create_refund(
            self.sale,
            reason='First unit',
            user=self.user,
            items=[{'sale_item_id': self.line.id, 'quantity': 1}],
        )
        with self.assertRaises(ValidationError):
            self.service.create_refund(
                self.sale,
                reason='Over refund',
                user=self.user,
                items=[{'sale_item_id': self.line.id, 'quantity': 2}],
            )

    def test_holding_sale_cannot_be_refunded(self):
        holding = Sale.objects.create(
            sale_number='S-HOLD',
            status='holding',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('0'),
        )
        with self.assertRaises(ValidationError):
            self.service.create_refund(holding, reason='Nope', user=self.user, full=True)

    def test_reason_required(self):
        with self.assertRaises(ValidationError):
            self.service.create_refund(self.sale, reason='  ', user=self.user, full=True)

    def test_full_refund_reverses_pay_later_customer_debt(self):
        from sales.models import Customer, CustomerWalletTransaction

        customer = Customer.objects.create(name='Debtor', phone='0700111222')
        customer.wallet_balance = Decimal('-100')
        customer.save(update_fields=['wallet_balance'])

        debt_sale = Sale.objects.create(
            sale_number='S-REF-DEBT',
            status='completed',
            subtotal=Decimal('100'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100'),
            payment_method='cash',
            amount_paid=Decimal('0'),
            cashier=self.user,
            customer=customer,
        )
        SaleItem.objects.create(
            sale=debt_sale,
            product=self.product,
            quantity=2,
            unit_price=Decimal('50'),
            subtotal=Decimal('100'),
        )
        CustomerWalletTransaction.objects.create(
            customer=customer,
            transaction_type='debit',
            source_type='debt',
            amount=Decimal('100'),
            balance_after=Decimal('-100'),
            sale=debt_sale,
            reference=debt_sale.sale_number,
            notes='Pay later',
            created_by=self.user,
        )

        refund = self.service.create_refund(
            debt_sale,
            reason='Wrong customer — void sale',
            user=self.user,
            full=True,
        )
        self.assertEqual(refund.amount, Decimal('100'))
        customer.refresh_from_db()
        self.assertEqual(customer.wallet_balance, Decimal('0'))
        self.assertTrue(
            CustomerWalletTransaction.objects.filter(
                sale=debt_sale,
                source_type='refund',
                transaction_type='credit',
                amount=Decimal('100'),
            ).exists()
        )


class SaleItemRefundableQuantitySerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('serializer_refund', password='x')
        cls.cat = Category.objects.create(name='SerCat', is_active=True)
        cls.product = Product.objects.create(
            name='SerProduct',
            sku='SER-1',
            category=cls.cat,
            price=Decimal('30'),
            stock_quantity=5,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-SER-1',
            status='completed',
            subtotal=Decimal('60'),
            total=Decimal('60'),
            payment_method='cash',
            amount_paid=Decimal('60'),
            cashier=cls.user,
        )
        cls.line = SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('30'),
            subtotal=Decimal('60'),
        )

    def test_sale_item_serializer_exposes_refundable_quantities(self):
        from sales.serializers import SaleSerializer

        SaleRefundService().create_refund(
            self.sale,
            reason='One returned',
            user=self.user,
            items=[{'sale_item_id': self.line.id, 'quantity': 1}],
        )
        data = SaleSerializer(self.sale).data
        item = data['items'][0]
        self.assertEqual(item['quantity_refunded'], 1)
        self.assertEqual(item['refundable_quantity'], 1)


class SaleRefundAPITests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ensure_permissions()
        sync_default_roles()

        cls.cat = Category.objects.create(name='APICat', is_active=True)
        cls.product = Product.objects.create(
            name='API Ref',
            sku='API-REF',
            category=cls.cat,
            price=Decimal('20'),
            stock_quantity=5,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-API-REF',
            status='completed',
            subtotal=Decimal('40'),
            total=Decimal('40'),
            payment_method='cash',
            amount_paid=Decimal('40'),
            cashier=cls.manager_user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('20'),
            subtotal=Decimal('40'),
        )

    def setUp(self):
        super().setUp()
        disable_maker_checker()

    def tearDown(self):
        disable_maker_checker()
        super().tearDown()

    def test_refund_endpoint_creates_audit_log(self):
        resp = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Wrong item sold', 'full': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIn('refund_number', resp.data)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.refund_status, 'refunded')
        self.assertTrue(
            AuditLog.objects.filter(module='sales', action='refund').exists()
        )

    def test_get_sale_includes_refundable_quantity_on_items(self):
        line = self.sale.items.first()
        partial = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {
                'reason': 'One damaged',
                'full': False,
                'items': [{'sale_item_id': line.id, 'quantity': 1}],
            },
            format='json',
        )
        self.assertEqual(partial.status_code, status.HTTP_201_CREATED, partial.data)

        detail = self.client.get(f'/api/sales/{self.sale.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        item = detail.data['items'][0]
        self.assertEqual(item['quantity_refunded'], 1)
        self.assertEqual(item['refundable_quantity'], 1)
        self.assertEqual(detail.data['refund_status'], 'partial')
        self.assertGreater(Decimal(str(detail.data['refundable_remaining'])), 0)

    def test_partial_refund_duplicate_excess_line_restores_stock_only_for_refunded_qty(self):
        """Refund only the duplicate row — first line per product stays on the sale."""
        keeper = self.sale.items.first()
        duplicate = SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('20'),
            subtotal=Decimal('20'),
        )
        self.sale.subtotal = Decimal('60')
        self.sale.total = Decimal('60')
        self.sale.save(update_fields=['subtotal', 'total'])
        stock_before = self.product.stock_quantity

        resp = self.client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {
                'reason': 'Duplicate invoice line',
                'full': False,
                'items': [{'sale_item_id': duplicate.id, 'quantity': 1}],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        keeper.refresh_from_db()
        self.assertEqual(keeper.quantity, 2)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, stock_before + 1)

        detail = self.client.get(f'/api/sales/{self.sale.id}/')
        by_id = {row['id']: row for row in detail.data['items']}
        self.assertEqual(by_id[keeper.id]['quantity_refunded'], 0)
        self.assertEqual(by_id[keeper.id]['refundable_quantity'], 2)
        self.assertEqual(by_id[duplicate.id]['quantity_refunded'], 1)
        self.assertEqual(by_id[duplicate.id]['refundable_quantity'], 0)

    def test_sales_without_refund_permission_denied(self):
        sales_user = User.objects.create_user('no_refund', password='x')
        sales_role = Role.objects.get(name=ROLE_SALES)
        UserProfile.objects.create(
            user=sales_user,
            role='cashier',
            custom_role=sales_role,
            is_active=True,
        )
        client = self.client.__class__()
        token = RefreshToken.for_user(sales_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.post(
            f'/api/sales/{self.sale.id}/refund/',
            {'reason': 'Should fail', 'full': True},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class SaleRefundAuditEventTests(TestCase):
    def test_log_sale_refunded(self):
        from rest_framework.test import APIRequestFactory
        from utils.audit_events import log_sale_refunded

        user = User.objects.create_user('aud', password='x')
        sale = Sale.objects.create(
            sale_number='S-AUD',
            status='completed',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
        )
        refund = SaleRefund.objects.create(
            sale=sale,
            refund_number='RF-TEST',
            refund_type='full',
            amount=Decimal('10'),
            reason='Test',
            refunded_by=user,
        )
        django_req = APIRequestFactory().post('/api/sales/1/refund/')
        django_req.user = user
        log_sale_refunded(django_req, sale, refund)
        row = AuditLog.objects.filter(module='sales', action='refund').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.changes.get('refund_number'), 'RF-TEST')
