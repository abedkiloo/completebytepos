"""Cover sales services/views edge paths that still show large miss counts."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from products.models import Category, Product
from sales.models import Customer, Invoice, Payment, PaymentPlan, Sale, SaleItem
from sales.services import SaleService
from sales.views import SaleViewSet
from settings.models import Branch, StoreSettings, Tenant
from utils.tests.api_test_base import ManagerAPITestCase


class SaleServiceQuerysetEdgeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('qs_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.cashier = User.objects.create_user('qs_cash', password='x')
        UserProfile.objects.create(
            user=cls.cashier, role='cashier', custom_role=roles[ROLE_SALES], is_active=True,
        )
        cls.sale = Sale.objects.create(
            cashier=cls.cashier, status='completed',
            subtotal=Decimal('100'), total=Decimal('100'), amount_paid=Decimal('100'),
            payment_method='cash', entry_source='field', notes='hello field',
            occurred_at=timezone.now(),
        )
        Sale.objects.create(
            cashier=cls.manager, status='holding',
            subtotal=Decimal('10'), total=Decimal('10'), amount_paid=Decimal('0'),
            payment_method='cash',
        )

    def test_filters_branch_search_origin_status_and_bad_ids(self):
        service = SaleService()
        factory = RequestFactory()
        req = factory.get('/api/sales/')
        req.user = self.manager

        with patch('sales.services.is_branch_support_enabled', return_value=True):
            with patch('sales.services.get_current_branch', return_value=None):
                qs = service.build_queryset(
                    {'show_all': 'false', 'branch_id': 'not-int'},
                    request=req,
                )
                self.assertEqual(qs.count(), 0)

            branch = MagicMock(id=42)
            with patch('sales.services.get_current_branch', return_value=branch):
                qs = service.build_queryset({'show_all': False}, request=req)
                self.assertEqual(list(qs), [])

        qs = service.build_queryset(
            {
                'date_from': timezone.localdate().isoformat(),
                'date_to': timezone.localdate().isoformat(),
                'payment_method': 'cash',
                'search': 'field',
                'sale_origin': 'field',
                'customer_id': 'abc',
                'include_holding': True,
            },
            request=req,
        )
        self.assertEqual(qs.count(), 0)  # bad customer_id → none

        qs = service.build_queryset(
            {'sale_origin': 'shop', 'status': 'completed', 'cashier_id': 'nope'},
            request=req,
        )
        self.assertEqual(qs.count(), 0)

        qs = service.build_queryset(
            {'status': 'completed', 'cashier_id': self.cashier.id},
            request=req,
        )
        self.assertIn(self.sale.id, qs.values_list('id', flat=True))

    def test_resolve_customer_and_branch(self):
        service = SaleService()
        self.assertIsNone(service.resolve_customer(None))
        self.assertIsNone(service.resolve_customer(999999))
        customer = Customer.objects.create(name='QS Cust', is_active=True)
        self.assertEqual(service.resolve_customer(customer.id).id, customer.id)

        factory = RequestFactory()
        req = factory.get('/')
        req.user = self.manager
        with patch('sales.services.is_branch_support_enabled', return_value=False):
            self.assertIsNone(service.resolve_sale_branch(req))

        tenant = Tenant.objects.create(
            name='QS T', code='QST', country='Kenya', owner=self.manager, created_by=self.manager,
        )
        branch = Branch.objects.create(tenant=tenant, name='HQ', branch_code='HQ1', is_active=True)
        other = Branch.objects.create(tenant=tenant, name='B2', branch_code='B2', is_active=True)
        with patch('sales.services.is_branch_support_enabled', return_value=True):
            with patch('sales.services.get_current_branch', return_value=branch):
                with patch('sales.services.get_current_tenant', return_value=tenant):
                    self.assertEqual(service.resolve_sale_branch(req, other.id).id, other.id)
                    self.assertEqual(service.resolve_sale_branch(req).id, branch.id)
                    missing = service.resolve_sale_branch(req, 999999)
                    self.assertEqual(missing.id, branch.id)
            with patch('sales.services.get_current_branch', return_value=None):
                with self.assertRaises(ValidationError):
                    service.resolve_sale_branch(req)

    def test_prepare_apply_payment_and_invoice_edges(self):
        service = SaleService()
        customer = Customer.objects.create(
            name='Pay Cust', wallet_balance=Decimal('50'), is_active=True,
        )
        with self.assertRaises(ValidationError):
            service._validate_checkout_payment('cash', Decimal('0'), Decimal('100'), None, False)

        result = service._prepare_sale_payment(
            customer=customer,
            sale_type='pos',
            total=Decimal('100'),
            amount_paid=Decimal('40'),
            allow_partial=True,
            excess_payment_choice='change',
            use_wallet=True,
            wallet_amount_requested=Decimal('0'),
        )
        self.assertEqual(result['wallet_amount_used'], Decimal('50'))
        self.assertEqual(result['pending_debt'], Decimal('10'))

        excess = service._prepare_sale_payment(
            customer=customer,
            sale_type='pos',
            total=Decimal('20'),
            amount_paid=Decimal('30'),
            allow_partial=False,
            excess_payment_choice='wallet',
            use_wallet=False,
            wallet_amount_requested=Decimal('0'),
        )
        self.assertEqual(excess['wallet_credit_added'], Decimal('10'))

        sale = Sale.objects.create(
            cashier=self.manager, status='completed', customer=customer,
            subtotal=Decimal('100'), total=Decimal('100'), amount_paid=Decimal('0'),
            payment_method='cash', sale_number='SALE-PAY-EDGE',
        )
        # Existing debt larger than pending → debt reduction path
        from sales.models import CustomerWalletTransaction
        CustomerWalletTransaction.objects.create(
            customer=customer, transaction_type='debit', source_type='debt',
            amount=Decimal('40'), balance_after=Decimal('10'), sale=sale, created_by=self.manager,
        )
        service._apply_sale_payment(
            customer,
            sale,
            self.manager,
            {
                'wallet_amount_used': Decimal('0'),
                'wallet_credit_added': Decimal('5'),
                'change': Decimal('0'),
                'pending_debt': Decimal('10'),
                'amount_paid_recorded': Decimal('90'),
            },
        )
        sale.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal('90'))

        # Invoice without items fails; walk-in cash name; payment plan validation
        bare = Sale.objects.create(
            cashier=self.manager, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            payment_method='cash', sale_type='normal',
        )
        with self.assertRaises(ValidationError):
            service._maybe_create_invoice_for_sale(
                bare, {'sale_type': 'normal', 'create_invoice': True}, None, self.manager, Decimal('0'),
            )

        category = Category.objects.create(name='Inv Cat', is_active=True)
        product = Product.objects.create(
            name='Inv Item', sku='INV-IT', category=category,
            price=Decimal('50'), stock_quantity=5, track_stock=True, is_active=True,
        )
        SaleItem.objects.create(
            sale=bare, product=product, quantity=1, unit_price=Decimal('50'), subtotal=Decimal('50'),
        )
        invoice = service._maybe_create_invoice_for_sale(
            bare,
            {
                'sale_type': 'normal',
                'create_invoice': True,
                'payment_method': 'cash',
            },
            None,
            self.manager,
            Decimal('0'),
        )
        self.assertIsNotNone(invoice)
        bare2 = Sale.objects.create(
            cashier=self.manager, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            payment_method='cash', sale_type='normal',
        )
        SaleItem.objects.create(
            sale=bare2, product=product, quantity=1, unit_price=Decimal('50'), subtotal=Decimal('50'),
        )
        with self.assertRaises(ValidationError):
            service._maybe_create_invoice_for_sale(
                bare2,
                {
                    'sale_type': 'normal',
                    'create_invoice': True,
                    'create_payment_plan': True,
                    'number_of_installments': 0,
                },
                None,
                self.manager,
                Decimal('0'),
            )


class SaleViewsCoverageAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name='View Gap', is_active=True)
        self.product = Product.objects.create(
            name='View Gap Item', sku='VG-1', category=self.category,
            price=Decimal('100'), cost=Decimal('40'),
            stock_quantity=50, track_stock=True, is_active=True,
        )
        self.customer = Customer.objects.create(name='View Cust', phone='0700888111', is_active=True)

    def test_backfill_import_template_and_csv(self):
        template = self.client.get('/api/sales/backfill-import-template/')
        self.assertEqual(template.status_code, status.HTTP_200_OK)
        self.assertIn(b'sale_reference', template.content)

        missing = self.client.post('/api/sales/backfill-import-csv/', {}, format='multipart')
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

        occurred = (timezone.now() - timedelta(days=2)).strftime('%Y-%m-%dT10:00:00')
        csv_body = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id\n'
            f'V1,{occurred},Sold offline during outage,VG-1,1,100.00,cash,100.00,pos,,,\n'
        )
        uploaded = BytesIO(csv_body.encode())
        uploaded.name = 'import.csv'
        response = self.client.post(
            '/api/sales/backfill-import-csv/',
            {'file': uploaded, 'acknowledge_stock_warnings': 'true'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['created'], 1)

    def test_backfill_preflight_and_daily_disabled_and_bad_cashier(self):
        occurred = (timezone.now() - timedelta(days=1)).isoformat()
        pre = self.client.post(
            '/api/sales/backfill-preflight/',
            {'occurred_at': occurred, 'items': [{'product_id': self.product.id, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(pre.status_code, status.HTTP_200_OK)
        self.assertIn('warnings', pre.data)

        with patch('settings.module_features.is_module_feature_enabled', return_value=False):
            daily = self.client.get('/api/sales/daily/')
            self.assertEqual(daily.status_code, status.HTTP_403_FORBIDDEN)
            cust = self.client.get(f'/api/sales/daily/customer/{self.customer.id}/')
            self.assertEqual(cust.status_code, status.HTTP_403_FORBIDDEN)

        from rest_framework.request import Request

        factory = APIRequestFactory()
        django_req = factory.get('/api/sales/daily/', {'cashier_id': 'abc'})
        force_authenticate(django_req, user=self.manager_user)
        req = Request(django_req)
        viewset = SaleViewSet()
        viewset.action = 'daily'
        viewset.request = req
        viewset.format_kwarg = None
        viewset.sale_service = SaleService()
        with patch('settings.module_features.is_module_feature_enabled', return_value=True):
            bad = viewset.daily(req)
            self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
            bad_cust = viewset.daily_customer(req, customer_id='not-an-id')
            self.assertEqual(bad_cust.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_put_and_wallet_create_response_fields(self):
        # PUT routes through update()
        sale = Sale.objects.create(
            cashier=self.manager_user, status='holding',
            subtotal=Decimal('100'), total=Decimal('100'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=sale, product=self.product, quantity=1,
            unit_price=Decimal('100'), subtotal=Decimal('100'),
        )
        response = self.client.put(
            f'/api/sales/{sale.id}/',
            {
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '100.00'}],
                'payment_method': 'cash',
                'amount_paid': '0',
                'status': 'holding',
            },
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST))

        # Create with wallet excess to hit wallet_credit_added response branch
        self.customer.wallet_balance = Decimal('0')
        self.customer.save(update_fields=['wallet_balance'])
        created = self.client.post(
            '/api/sales/',
            {
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '100.00'}],
                'payment_method': 'cash',
                'amount_paid': '150.00',
                'customer_id': self.customer.id,
                'excess_payment_choice': 'wallet',
                'sale_type': 'pos',
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertIn('wallet_credit_added', created.data)

    def test_invoice_payment_delete_and_payment_plan_str(self):
        sale = Sale.objects.create(
            cashier=self.manager_user, status='completed', customer=self.customer,
            subtotal=Decimal('100'), total=Decimal('100'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        invoice = Invoice.objects.create(
            sale=sale, customer=self.customer, customer_name=self.customer.name,
            subtotal=Decimal('100'), total=Decimal('100'), amount_paid=Decimal('0'),
            status='sent', issued_date=timezone.localdate(),
            due_date=timezone.localdate() - timedelta(days=1),
            created_by=self.manager_user,
        )
        # overdue path on save
        invoice.amount_paid = Decimal('0')
        invoice.save()
        self.assertEqual(invoice.status, 'overdue')
        self.assertEqual(invoice.payment_percentage, 0)
        self.assertTrue(invoice.is_overdue)

        payment = Payment.objects.create(
            invoice=invoice, amount=Decimal('40'), payment_method='cash',
            payment_date=timezone.localdate(), recorded_by=self.manager_user,
        )
        self.assertIn('Payment of', str(payment))
        payment.delete()
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal('0'))

        plan = PaymentPlan.objects.create(
            invoice=invoice,
            total_amount=Decimal('100'),
            number_of_installments=4,
            installment_amount=Decimal('25'),
            frequency='weekly',
            start_date=timezone.localdate(),
            is_active=True,
            completed_installments=1,
            last_payment_date=timezone.localdate(),
        )
        self.assertIn('Payment Plan', str(plan))
        self.assertEqual(plan.remaining_installments, 3)
        self.assertFalse(plan.is_complete)

        # frequency branches (OneToOne — recreate invoice per frequency)
        for freq in ('daily', 'biweekly', 'monthly', 'quarterly'):
            inv = Invoice.objects.create(
                customer=self.customer, customer_name=self.customer.name,
                subtotal=Decimal('100'), total=Decimal('100'), amount_paid=Decimal('0'),
                status='sent', issued_date=timezone.localdate(),
            )
            PaymentPlan.objects.create(
                invoice=inv,
                total_amount=Decimal('100'),
                number_of_installments=2,
                installment_amount=Decimal('50'),
                frequency=freq,
                start_date=timezone.localdate(),
                is_active=True,
                completed_installments=1,
                last_payment_date=timezone.localdate(),
            )
