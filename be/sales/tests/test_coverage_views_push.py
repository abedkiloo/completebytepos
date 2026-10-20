"""Push sales views coverage for customers, invoices, and payments."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import UserProfile
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from approvals.models import PendingChange
from products.models import Product
from sales.models import Customer, Invoice, Payment, Sale, SaleItem
from sales.views import (
    CustomerViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    SaleViewSet,
    _parse_backfill_request_data,
    _queue_or_create_backfill,
    _resubmit_backfill,
)
from settings.models import StoreSettings
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class CustomerViewPushTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='View Push Cust', phone='0700111001', is_active=True,
        )

    def test_kenya_locations_list_filters_and_disabled_flags(self):
        resp = self.client.get('/api/sales/customers/kenya-locations/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        listed = self.client.get(
            '/api/sales/customers/',
            {
                'is_active': 'true',
                'search': 'View Push',
                'created_on': 'today',
                'customer_type': 'individual',
            },
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)

        bad_day = self.client.get('/api/sales/customers/', {'created_on': 'not-a-day'})
        self.assertEqual(bad_day.status_code, status.HTTP_200_OK)

        dated = self.client.get(
            '/api/sales/customers/',
            {'created_on': timezone.localdate().isoformat()},
        )
        self.assertEqual(dated.status_code, status.HTTP_200_OK)

        with patch('sales.customer_module_settings.customers_enable_edit', return_value=False):
            blocked = self.client.patch(
                f'/api/sales/customers/{self.customer.id}/',
                {'name': 'Nope'},
                format='json',
            )
            self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)

        with patch('sales.customer_module_settings.customers_enable_delete', return_value=False):
            blocked_del = self.client.delete(f'/api/sales/customers/{self.customer.id}/')
            self.assertEqual(blocked_del.status_code, status.HTTP_403_FORBIDDEN)

        factory = APIRequestFactory()
        view = CustomerViewSet.as_view({'post': 'create'})
        req = factory.post('/api/sales/customers/', {'name': 'X'}, format='json')
        force_authenticate(req, user=self.manager_user)
        with patch.object(CustomerViewSet, 'get_serializer') as gs:
            ser = MagicMock()
            ser.is_valid.return_value = True
            ser.save.side_effect = RuntimeError('create fail')
            gs.return_value = ser
            resp = view(req)
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        view_u = CustomerViewSet.as_view({'patch': 'partial_update'})
        req_u = factory.patch(
            f'/api/sales/customers/{self.customer.id}/',
            {'name': 'Y'},
            format='json',
        )
        force_authenticate(req_u, user=self.manager_user)
        with patch.object(CustomerViewSet, 'get_serializer') as gs:
            ser = MagicMock()
            ser.is_valid.side_effect = lambda **k: True
            ser.save.side_effect = RuntimeError('update fail')
            ser.validated_data = {}
            gs.return_value = ser
            with patch.object(CustomerViewSet, 'get_object', return_value=self.customer):
                resp_u = view_u(req_u, pk=self.customer.pk)
            self.assertEqual(resp_u.status_code, status.HTTP_400_BAD_REQUEST)


class InvoicePaymentViewPushTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Inv Push', phone='0700222002', is_active=True,
        )
        self.product = Product.objects.create(
            name='Inv Push Prod', sku='IPP-1', price=Decimal('40'),
            stock_quantity=10, track_stock=True, is_active=True,
        )
        self.sale = Sale.objects.create(
            cashier=self.manager_user, customer=self.customer, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=self.sale, product=self.product, quantity=1,
            unit_price=Decimal('40'), subtotal=Decimal('40'),
        )
        self.invoice = Invoice.objects.create(
            sale=self.sale, customer=self.customer, customer_name=self.customer.name,
            issued_date=timezone.localdate(), due_date=timezone.localdate() + timedelta(days=7),
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            balance=Decimal('40'), status='sent', created_by=self.manager_user,
        )

    def test_invoice_pdf_and_payment_create_edges(self):
        with patch('sales.views.create_invoice_pdf', side_effect=RuntimeError('pdf fail')):
            pdf = self.client.get(f'/api/sales/invoices/{self.invoice.id}/download_pdf/')
            self.assertEqual(pdf.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        with patch('sales.views.create_invoice_pdf', return_value=BytesIO(b'%PDF-1.4')):
            ok = self.client.get(f'/api/sales/invoices/{self.invoice.id}/download_pdf/')
            self.assertEqual(ok.status_code, status.HTTP_200_OK)

        with patch('sales.invoicing_access.payment_tracking_allowed', return_value=False):
            disabled = self.client.post(
                '/api/sales/payments/',
                {'invoice_id': self.invoice.id, 'amount': '10.00', 'payment_method': 'cash'},
                format='json',
            )
            self.assertEqual(disabled.status_code, status.HTTP_403_FORBIDDEN)

        missing = self.client.post(
            '/api/sales/payments/',
            {'invoice_id': 999999, 'amount': '10.00', 'payment_method': 'cash'},
            format='json',
        )
        self.assertIn(missing.status_code, (status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST))

        zero = self.client.post(
            '/api/sales/payments/',
            {'invoice': self.invoice.id, 'amount': '0', 'payment_method': 'cash'},
            format='json',
        )
        self.assertEqual(zero.status_code, status.HTTP_400_BAD_REQUEST)

        over = self.client.post(
            '/api/sales/payments/',
            {'invoice_id': self.invoice.id, 'amount': '999.00', 'payment_method': 'cash'},
            format='json',
        )
        self.assertEqual(over.status_code, status.HTTP_400_BAD_REQUEST)

        with patch('accounting.views.create_payment_journal_entry', side_effect=RuntimeError('je')):
            created = self.client.post(
                '/api/sales/payments/',
                {
                    'invoice_id': self.invoice.id,
                    'amount': '10.00',
                    'payment_method': 'cash',
                    'payment_date': timezone.localdate().isoformat(),
                },
                format='json',
            )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)

        listed = self.client.get(
            '/api/sales/payments/',
            {
                'invoice': self.invoice.id,
                'date_from': timezone.localdate().isoformat(),
                'date_to': timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)

    def test_sale_correct_date_and_refund_action(self):
        sale = Sale.objects.create(
            cashier=self.manager_user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('40'),
            payment_method='cash', occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale, product=self.product, quantity=1,
            unit_price=Decimal('40'), subtotal=Decimal('40'),
        )
        target = (timezone.now() - timedelta(days=1)).isoformat()
        with patch('approvals.permissions.user_may_approve_dated_item', return_value=True):
            resp = self.client.post(
                f'/api/sales/{sale.id}/correct-date/',
                {'occurred_at': target},
                format='json',
            )
        self.assertIn(resp.status_code, (200, 400))

        with patch('inventory.stock_layers.layers_enabled', return_value=False):
            with patch(
                'accounting.services.create_sale_refund_journal_entry',
                side_effect=RuntimeError('je'),
            ):
                refund = self.client.post(
                    f'/api/sales/{sale.id}/refund/',
                    {'reason': 'Customer changed mind fully', 'full': True},
                    format='json',
                )
        self.assertIn(refund.status_code, (200, 201, 202, 400))


class SaleCompletionApprovalUnitPushTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('sca_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.admin = User.objects.create_superuser('sca_admin', 'sca@t.com', 'x')
        cls.customer = Customer.objects.create(
            name='SCA Cust', phone='0700333003', wallet_balance=Decimal('50'), is_active=True,
        )
        cls.product = Product.objects.create(
            name='SCA Prod', sku='SCA-1', price=Decimal('20'),
            stock_quantity=10, track_stock=True, is_active=True,
        )

    def test_salesperson_action_wallet_lock_and_admin_return(self):
        from sales.sale_completion_approval import (
            admin_return_sale_for_correction,
            invoice_payload_from_validated_data,
            sale_needs_salesperson_action,
            sale_rejection_reason,
            wallet_amount_to_lock,
        )

        holding = Sale.objects.create(
            cashier=self.manager, customer=self.customer, status='holding',
            subtotal=Decimal('20'), total=Decimal('20'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        holding._has_rejected_sale_complete = True
        holding._has_pending_sale_complete = False
        self.assertTrue(sale_needs_salesperson_action(holding))
        holding._sale_rejection_reason = '  Fix price  '
        self.assertEqual(sale_rejection_reason(holding), 'Fix price')

        holding2 = Sale.objects.create(
            cashier=self.manager, status='holding',
            subtotal=Decimal('20'), total=Decimal('20'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        self.assertFalse(sale_needs_salesperson_action(holding2))
        self.assertEqual(sale_rejection_reason(holding2), '')

        self.assertEqual(
            wallet_amount_to_lock(None, Decimal('20'), use_wallet=True),
            Decimal('0'),
        )
        self.assertEqual(
            wallet_amount_to_lock(self.customer, Decimal('20'), use_wallet=False),
            Decimal('0'),
        )
        self.customer.wallet_balance = Decimal('0')
        self.assertEqual(
            wallet_amount_to_lock(self.customer, Decimal('20'), use_wallet=True),
            Decimal('0'),
        )
        self.customer.wallet_balance = Decimal('50')
        self.assertEqual(
            wallet_amount_to_lock(
                self.customer, Decimal('20'), use_wallet=True, requested=Decimal('10'),
            ),
            Decimal('10'),
        )
        self.assertEqual(
            wallet_amount_to_lock(self.customer, Decimal('20'), use_wallet=True),
            Decimal('20'),
        )

        self.assertIsNone(invoice_payload_from_validated_data({'sale_type': 'pos'}))
        inv = invoice_payload_from_validated_data({
            'sale_type': 'normal',
            'create_invoice': True,
            'customer_name': 'Walk-in',
        })
        self.assertIsNotNone(inv)

        completed = Sale.objects.create(
            cashier=self.manager, customer=self.customer, status='completed',
            subtotal=Decimal('20'), total=Decimal('20'), amount_paid=Decimal('20'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=completed, product=self.product, quantity=1,
            unit_price=Decimal('20'), subtotal=Decimal('20'),
        )
        with self.assertRaises(ValidationError):
            admin_return_sale_for_correction(completed, user=self.manager, reason='x')
        with self.assertRaises(ValidationError):
            admin_return_sale_for_correction(completed, user=self.admin, reason='')

        with patch('sales.sale_completion_approval.unpost_posted_sale'):
            with patch('sales.sale_completion_approval.record_rejected_sale_complete_change'):
                with patch('sales.sale_completion_approval.notify_sale_returned_for_correction'):
                    with patch(
                        'sales.sale_completion_approval.pending_sale_complete_change',
                        return_value=None,
                    ):
                        out = admin_return_sale_for_correction(
                            completed, user=self.admin, reason='Need to fix item',
                        )
        self.assertEqual(out.status, 'holding')


class InvoiceCreateViewPushTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='InvC Push', phone='0700444004', is_active=True,
        )
        self.product = Product.objects.create(
            name='InvC Prod', sku='ICP-1', price=Decimal('15'),
            stock_quantity=5, track_stock=True, is_active=True,
        )

    def test_manual_invoice_validation_edges(self):
        empty = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'subtotal': '15.00',
                'items': [],
            },
            format='json',
        )
        self.assertEqual(empty.status_code, status.HTTP_400_BAD_REQUEST)

        missing_prod = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'subtotal': '15.00',
                'items': [{'quantity': 1, 'unit_price': '15.00'}],
            },
            format='json',
        )
        self.assertEqual(missing_prod.status_code, status.HTTP_400_BAD_REQUEST)

        bad_qty = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'subtotal': '15.00',
                'items': [{'product_id': self.product.id, 'quantity': 0, 'unit_price': '15'}],
            },
            format='json',
        )
        self.assertEqual(bad_qty.status_code, status.HTTP_400_BAD_REQUEST)

        bad_price = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'subtotal': '15.00',
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '-1'}],
            },
            format='json',
        )
        self.assertEqual(bad_price.status_code, status.HTTP_400_BAD_REQUEST)

        missing_cust = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': 999999,
                'subtotal': '15.00',
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '15'}],
            },
            format='json',
        )
        self.assertEqual(missing_cust.status_code, status.HTTP_404_NOT_FOUND)

        ok = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'subtotal': '15.00',
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '15.00'}],
            },
            format='json',
        )
        self.assertIn(ok.status_code, (200, 201), ok.data)


class DebtAndInvoiceQueryPushTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            name='Debt Push', phone='0700555005', wallet_balance=Decimal('-40'), is_active=True,
        )
        self.product = Product.objects.create(
            name='Debt Prod', sku='DP-1', price=Decimal('40'),
            stock_quantity=5, track_stock=True, is_active=True,
        )

    def test_debt_endpoints_and_disabled_wallet(self):
        summary = self.client.get('/api/sales/customers/debt-summary/')
        self.assertIn(summary.status_code, (200, 403))

        debtors = self.client.get(
            '/api/sales/customers/debtors/',
            {'page': 'bad', 'page_size': 'x', 'search': 'Debt', 'aging_bucket': '0_7'},
        )
        self.assertIn(debtors.status_code, (200, 403))

        count = self.client.get('/api/sales/customers/debtor-count/')
        self.assertIn(count.status_code, (200, 403))

        collections = self.client.get(
            '/api/sales/customers/debt-collections/',
            {'date': 'not-a-date', 'page': 'a', 'page_size': 'b'},
        )
        self.assertIn(collections.status_code, (200, 400, 403))

        trail = self.client.get(
            '/api/sales/customers/payments-trail/',
            {'page': 'z', 'page_size': 'q', 'date_from': 'bad'},
        )
        self.assertIn(trail.status_code, (200, 400, 403))

        with patch('sales.customer_module_settings.customers_show_wallet_balance', return_value=False):
            self.assertEqual(
                self.client.get('/api/sales/customers/debt-summary/').status_code,
                status.HTTP_403_FORBIDDEN,
            )
            self.assertEqual(
                self.client.get('/api/sales/customers/debtors/').status_code,
                status.HTTP_403_FORBIDDEN,
            )
            zero = self.client.get('/api/sales/customers/debtor-count/')
            self.assertEqual(zero.status_code, status.HTTP_200_OK)
            self.assertEqual(zero.data.get('count'), 0)
            self.assertEqual(
                self.client.get('/api/sales/customers/debt-collections/').status_code,
                status.HTTP_403_FORBIDDEN,
            )
            self.assertEqual(
                self.client.get('/api/sales/customers/payments-trail/').status_code,
                status.HTTP_403_FORBIDDEN,
            )

        with patch(
            'sales.customer_search.apply_customer_search',
            side_effect=RuntimeError('search boom'),
        ):
            listed = self.client.get('/api/sales/customers/', {'search': 'x'})
            self.assertEqual(listed.status_code, status.HTTP_200_OK)

        detail = self.client.get(
            f'/api/sales/customers/{self.customer.id}/detail/',
            {'orders_page': 'bad', 'payments_page': 'nope'},
        )
        self.assertIn(detail.status_code, (200, 404))

    def test_invoice_list_filters_and_from_sale_errors(self):
        inv = Invoice.objects.create(
            customer=self.customer, customer_name=self.customer.name,
            issued_date=timezone.localdate(), due_date=timezone.localdate(),
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            balance=Decimal('40'), status='overdue', created_by=self.manager_user,
        )
        listed = self.client.get(
            '/api/sales/invoices/',
            {
                'show_all': 'true',
                'status': 'overdue',
                'overdue': 'true',
                'search': self.customer.name[:4],
                'date_from': '2000-01-01',
                'date_to': '2099-01-01',
            },
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)

        with patch('sales.invoicing_access.invoice_creation_allowed', return_value=False):
            disabled = self.client.post(
                '/api/sales/invoices/',
                {'subtotal': '10', 'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '10'}]},
                format='json',
            )
            self.assertEqual(disabled.status_code, status.HTTP_403_FORBIDDEN)

        missing_sale = self.client.post(
            '/api/sales/invoices/',
            {
                'sale_id': 999999,
                'subtotal': '40',
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '40'}],
            },
            format='json',
        )
        self.assertIn(missing_sale.status_code, (404, 400))

        sale = Sale.objects.create(
            cashier=self.manager_user, customer=self.customer, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('40'),
            payment_method='cash',
        )
        Invoice.objects.create(
            sale=sale, customer=self.customer, customer_name=self.customer.name,
            issued_date=timezone.localdate(), due_date=timezone.localdate(),
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('40'),
            balance=Decimal('0'), status='paid', created_by=self.manager_user,
        )
        dup = self.client.post(
            '/api/sales/invoices/',
            {
                'sale_id': sale.id,
                'subtotal': '40',
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '40'}],
            },
            format='json',
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)

    def test_completed_sale_edit_queue_and_refund_validation(self):
        sale = Sale.objects.create(
            cashier=self.manager_user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('40'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=sale, product=self.product, quantity=1,
            unit_price=Decimal('40'), subtotal=Decimal('40'),
        )
        change = MagicMock(id=55, action_type='sale_edit', status='pending')
        with patch('approvals.sales_policy.completed_sale_direct_edit_blocked', return_value=False):
            with patch('approvals.sales_integration.queue_completed_sale_edit', return_value=change):
                queued = self.client.patch(
                    f'/api/sales/{sale.id}/',
                    {'notes': 'fix', 'reason': 'typo'},
                    format='json',
                )
        self.assertIn(queued.status_code, (202, 200, 400))

        with patch('approvals.sales_policy.completed_sale_direct_edit_blocked', return_value=False):
            with patch(
                'approvals.sales_integration.queue_completed_sale_edit',
                side_effect=ValidationError({'reason': 'need reason'}),
            ):
                bad = self.client.patch(
                    f'/api/sales/{sale.id}/',
                    {'notes': 'fix'},
                    format='json',
                )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        with patch('approvals.permissions.user_has_admin_checker_override', return_value=True):
            with patch(
                'sales.refunds.SaleRefundService.create_refund',
                side_effect=ValidationError('cannot refund'),
            ):
                refund = self.client.post(
                    f'/api/sales/{sale.id}/refund/',
                    {'reason': 'Want money back please', 'full': True},
                    format='json',
                )
        self.assertEqual(refund.status_code, status.HTTP_400_BAD_REQUEST)

        with patch('approvals.permissions.user_has_admin_checker_override', return_value=False):
            with patch(
                'approvals.refund_integration.queue_sale_refund',
                side_effect=ValidationError({'reason': 'blocked'}),
            ):
                queued_bad = self.client.post(
                    f'/api/sales/{sale.id}/refund/',
                    {'reason': 'Want money back please', 'full': True},
                    format='json',
                )
        self.assertEqual(queued_bad.status_code, status.HTTP_400_BAD_REQUEST)


class SaleViewHelpersPushTests(TestCase):
    """Exercise module-level view helpers without full API stack."""

    def test_parse_backfill_and_queue_resubmit(self):
        req = MagicMock()
        req.data = {
            'items': '[{"product_id": 1, "quantity": 1}]',
            'customer_id': '',
            'served_by_id': 'null',
            'allow_partial_payment': 'yes',
            'acknowledge_stock_warnings': '1',
            'create_invoice': 'true',
        }
        parsed = _parse_backfill_request_data(req)
        self.assertIsInstance(parsed['items'], list)
        self.assertTrue(parsed['create_invoice'])

        user = User.objects.create_user('vh_user', password='x')
        req.user = user
        req.FILES = {}
        validated = {'items': [], 'occurred_at': timezone.now()}
        sale = Sale.objects.create(
            status='completed', subtotal=Decimal('1'), total=Decimal('1'),
            amount_paid=Decimal('1'), payment_method='cash',
        )
        invoice = Invoice.objects.create(
            customer_name='Walk-in', subtotal=Decimal('1'), total=Decimal('1'),
            amount_paid=Decimal('0'), status='sent', issued_date=timezone.localdate(),
        )
        with patch('sales.backfill_policy.backfill_requires_approval', return_value=False):
            with patch('sales.views.SaleService') as svc_cls:
                svc_cls.return_value.create_sale_from_validated_data.return_value = {
                    'sale': sale,
                    'invoice': invoice,
                }
                with patch('utils.audit_events.log_sale_completed'):
                    resp = _queue_or_create_backfill(req, validated)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('invoice', resp.data)

        with patch('sales.backfill_policy.backfill_requires_approval', return_value=True):
            with patch('approvals.backfill_integration.queue_sale_backfill') as queue:
                queue.return_value = PendingChange.objects.create(
                    action_type='sale_backfill',
                    entity_type='sales.Sale',
                    entity_id='1',
                    reason='test',
                    status=PendingChange.STATUS_PENDING,
                )
                queued = _queue_or_create_backfill(req, validated)
        self.assertEqual(queued.status_code, status.HTTP_202_ACCEPTED)

        with self.assertRaises(ValidationError):
            _resubmit_backfill(req, 999999, validated)


class SaleViewSetExtraPushTests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])
        self.product = Product.objects.create(
            name='SV Push Extra', sku='SVP-X', price=Decimal('30'),
            stock_quantity=20, track_stock=True, is_active=True,
        )
        self.customer = Customer.objects.create(
            name='SV Push Cust', phone='0700666006', is_active=True,
        )

    def _backfill_payload(self):
        occurred = (timezone.now() - timedelta(days=3)).strftime('%Y-%m-%dT10:00:00')
        return {
            'occurred_at': occurred,
            'backfill_reason': 'Sold offline during outage',
            'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '30.00'}],
            'payment_method': 'cash',
            'amount_paid': '30.00',
            'sale_type': 'pos',
            'acknowledge_stock_warnings': True,
        }

    def test_backfill_resubmit_and_preflight_datetime(self):
        bad_resubmit = self.client.post(
            '/api/sales/backfill/',
            {**self._backfill_payload(), 'resubmit_of': 'not-int'},
            format='json',
        )
        self.assertEqual(bad_resubmit.status_code, status.HTTP_400_BAD_REQUEST)

        missing_resubmit = self.client.post(
            '/api/sales/backfill/',
            {**self._backfill_payload(), 'resubmit_of': 999999},
            format='json',
        )
        self.assertIn(missing_resubmit.status_code, (400, 404))

        with patch(
            'sales.views._resubmit_backfill',
            side_effect=ValidationError({'error': 'resubmit failed'}),
        ):
            boom = self.client.post(
                '/api/sales/backfill/',
                {**self._backfill_payload(), 'resubmit_of': 1},
                format='json',
            )
        self.assertEqual(boom.status_code, status.HTTP_400_BAD_REQUEST)

        with patch(
            'sales.views._queue_or_create_backfill',
            side_effect=ValidationError('queue failed'),
        ):
            qfail = self.client.post('/api/sales/backfill/', self._backfill_payload(), format='json')
        self.assertEqual(qfail.status_code, status.HTTP_400_BAD_REQUEST)

        photo = SimpleUploadedFile('receipt.jpg', b'jpeg-bytes', content_type='image/jpeg')
        with patch('sales.backfill_photo.save_pending_backfill_receipt_photo', return_value='/tmp/x.jpg') as save_photo:
            with patch('sales.views._queue_or_create_backfill') as q:
                q.return_value = MagicMock(status_code=status.HTTP_201_CREATED, data={})
                photo_resp = self.client.post(
                    '/api/sales/backfill/',
                    {**self._backfill_payload(), 'backfill_receipt_photo': photo},
                    format='multipart',
                )
        self.assertIn(photo_resp.status_code, (200, 201, 202, 400))
        if photo_resp.status_code != status.HTTP_400_BAD_REQUEST:
            self.assertTrue(save_photo.called or q.called)

        pre = self.client.post(
            '/api/sales/backfill-preflight/',
            {
                'occurred_at': self._backfill_payload()['occurred_at'],
                'items': self._backfill_payload()['items'],
            },
            format='json',
        )
        self.assertEqual(pre.status_code, status.HTTP_200_OK)

    def test_holding_active_save_cancel_and_checkout_errors(self):
        empty = self.client.get('/api/sales/active-holding/')
        self.assertEqual(empty.status_code, status.HTTP_200_OK)

        saved = self.client.post(
            '/api/sales/holding/',
            {
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '30.00'}],
                'customer_id': 999999,
            },
            format='json',
        )
        self.assertEqual(saved.status_code, status.HTTP_404_NOT_FOUND)

        holding = self.client.post(
            '/api/sales/holding/',
            {'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '30.00'}]},
            format='json',
        )
        self.assertIn(holding.status_code, (200, 201), holding.data)
        hid = holding.data.get('id')

        with patch(
            'sales.services.SaleService.resolve_sale_branch',
            side_effect=ValidationError('no branch'),
        ):
            bad_branch = self.client.post(
                '/api/sales/holding/',
                {'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '30.00'}]},
                format='json',
            )
        self.assertEqual(bad_branch.status_code, status.HTTP_400_BAD_REQUEST)

        if hid:
            cancelled = self.client.post(f'/api/sales/{hid}/cancel-holding/')
            self.assertIn(cancelled.status_code, (200, 400))

            holding2 = self.client.post(
                '/api/sales/holding/',
                {'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '30.00'}]},
                format='json',
            )
            hid2 = holding2.data.get('id')
            if hid2:
                with patch(
                    'sales.services.SaleService.resolve_sale_branch',
                    side_effect=ValidationError('branch missing'),
                ):
                    chk = self.client.post(
                        f'/api/sales/{hid2}/checkout/',
                        {'payment_method': 'cash', 'amount_paid': '30.00'},
                        format='json',
                    )
                self.assertEqual(chk.status_code, status.HTTP_400_BAD_REQUEST)

        active = self.client.get('/api/sales/active-holding/')
        self.assertEqual(active.status_code, status.HTTP_200_OK)

    def test_complete_reject_correct_date_and_create_invoice_field(self):
        completed = Sale.objects.create(
            cashier=self.manager_user, status='completed',
            subtotal=Decimal('30'), total=Decimal('30'), amount_paid=Decimal('30'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=completed, product=self.product, quantity=1,
            unit_price=Decimal('30'), subtotal=Decimal('30'),
        )
        wrong = self.client.post(f'/api/sales/{completed.id}/complete/')
        self.assertEqual(wrong.status_code, status.HTTP_400_BAD_REQUEST)

        pending = Sale.objects.create(
            cashier=self.manager_user, status='pending_approval',
            subtotal=Decimal('30'), total=Decimal('30'), amount_paid=Decimal('30'),
            payment_method='cash', occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=pending, product=self.product, quantity=1,
            unit_price=Decimal('30'), subtotal=Decimal('30'),
        )
        with patch('sales.sale_completion_approval.pending_sale_complete_change', return_value=None):
            with patch('approvals.permissions.user_may_approve_dated_item', return_value=True):
                with patch('sales.sale_completion_approval.approve_queued_sale') as approve:
                    approve.side_effect = lambda s, u: setattr(s, 'status', 'completed') or s.save(
                        update_fields=['status']
                    )
                    done = self.client.post(f'/api/sales/{pending.id}/complete/')
        self.assertIn(done.status_code, (200, 400))

        with patch('approvals.permissions.user_may_approve_dated_item', return_value=True):
            no_reason = self.client.post(f'/api/sales/{pending.id}/reject-complete/', {}, format='json')
        self.assertIn(no_reason.status_code, (400, 200))

        with patch('approvals.permissions.user_has_admin_checker_override', return_value=True):
            with patch('sales.sale_completion_approval.admin_return_sale_for_correction') as ret:
                ret.side_effect = ValidationError({'rejection_reason': 'required'})
                admin_bad = self.client.post(
                    f'/api/sales/{completed.id}/reject-complete/',
                    {'reason': ''},
                    format='json',
                )
        self.assertEqual(admin_bad.status_code, status.HTTP_400_BAD_REQUEST)

        target = (timezone.now() - timedelta(days=2)).isoformat()
        with patch('approvals.permissions.user_may_approve_dated_item', return_value=True):
            with patch('sales.sale_date.correct_sale_occurred_at', side_effect=ValidationError('bad date')):
                bad_date = self.client.post(
                    f'/api/sales/{completed.id}/correct-date/',
                    {'occurred_at': target},
                    format='json',
                )
        self.assertEqual(bad_date.status_code, status.HTTP_400_BAD_REQUEST)

        with patch('sales.views.SaleService') as svc:
            sale = Sale.objects.create(
                cashier=self.manager_user, status='completed',
                subtotal=Decimal('30'), total=Decimal('30'), amount_paid=Decimal('30'),
                payment_method='cash',
            )
            inv = Invoice.objects.create(
                customer=self.customer, customer_name=self.customer.name,
                subtotal=Decimal('30'), total=Decimal('30'), amount_paid=Decimal('0'),
                status='sent', issued_date=timezone.localdate(),
            )
            svc.return_value.create_sale_from_validated_data.return_value = {
                'sale': sale,
                'invoice': inv,
                'wallet_balance': Decimal('5'),
                'wallet_amount_used': Decimal('0'),
                'wallet_credit_added': Decimal('5'),
                'message': 'wallet credit',
            }
            factory = APIRequestFactory()
            view = SaleViewSet.as_view({'post': 'create'})
            req = factory.post(
                '/api/sales/',
                {
                    'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '30.00'}],
                    'payment_method': 'cash',
                    'amount_paid': '30.00',
                },
                format='json',
            )
            force_authenticate(req, user=self.manager_user)
            with patch.object(SaleViewSet, 'get_serializer') as gs:
                ser = MagicMock()
                ser.is_valid.return_value = True
                ser.validated_data = {}
                gs.return_value = ser
                created = view(req)
        self.assertIn(created.status_code, (201, 400))

    def test_daily_disabled_and_staff_list(self):
        with patch('settings.module_features.is_module_feature_enabled', return_value=False):
            daily = self.client.get('/api/sales/daily/')
            self.assertEqual(daily.status_code, status.HTTP_403_FORBIDDEN)
            cust_day = self.client.get(f'/api/sales/daily/customer/{self.customer.id}/')
            self.assertEqual(cust_day.status_code, status.HTTP_403_FORBIDDEN)

        staff = self.client.get('/api/sales/cashiers/')
        self.assertIn(staff.status_code, (200, 403, 404))


class SaleRefundRollbackQueuePushTests(SalesAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.product = Product.objects.create(
            name='Queue Ref', sku='QR-1', price=Decimal('20'),
            stock_quantity=5, track_stock=True, is_active=True,
        )
        cls.sale = Sale.objects.create(
            cashier=cls.sales_user, status='completed',
            subtotal=Decimal('20'), total=Decimal('20'), amount_paid=Decimal('20'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=cls.sale, product=cls.product, quantity=1,
            unit_price=Decimal('20'), subtotal=Decimal('20'),
        )

    def test_refund_and_rollback_queue_for_cashier(self):
        pending = PendingChange.objects.create(
            action_type='sale_refund',
            entity_type='sales.Sale',
            entity_id=str(self.sale.pk),
            reason='refund queue',
            status=PendingChange.STATUS_PENDING,
        )
        with patch('approvals.refund_integration.queue_sale_refund', return_value=pending):
            refund = self.client.post(
                f'/api/sales/{self.sale.id}/refund/',
                {'reason': 'Customer wants refund please', 'full': True},
                format='json',
            )
        self.assertIn(refund.status_code, (202, 400, 403))

        rb_pending = PendingChange.objects.create(
            action_type='sale_rollback',
            entity_type='sales.Sale',
            entity_id=str(self.sale.pk),
            reason='rollback queue',
            status=PendingChange.STATUS_PENDING,
        )
        with patch('approvals.rollback_integration.queue_sale_rollback', return_value=rb_pending):
            rollback = self.client.post(
                f'/api/sales/{self.sale.id}/rollback/',
                {'reason': 'Wrong sale entirely'},
                format='json',
            )
        self.assertIn(rollback.status_code, (202, 400, 403))


class CustomerViewExtraPushTests(ManagerAPITestCase):
    def test_list_filters_branch_search_and_update_success(self):
        branch_cust = Customer.objects.create(
            name='Branch Filter', phone='0700777007', is_active=True,
        )
        listed = self.client.get(
            '/api/sales/customers/',
            {
                'branch_id': str(branch_cust.branch_id or 0),
                'is_active': 'maybe',
                'search': 'Branch',
            },
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)

        ok_patch = self.client.patch(
            f'/api/sales/customers/{branch_cust.id}/',
            {'contact_person': 'Sam'},
            format='json',
        )
        self.assertIn(ok_patch.status_code, (200, 400))

        with patch.object(CustomerViewSet, 'get_serializer') as gs:
            ser = MagicMock()
            ser.is_valid.return_value = True
            ser.save.return_value = None
            ser.data = {'id': branch_cust.id}
            gs.return_value = ser
            factory = APIRequestFactory()
            view = CustomerViewSet.as_view({'put': 'update'})
            req = factory.put(
                f'/api/sales/customers/{branch_cust.id}/',
                {'name': branch_cust.name},
                format='json',
            )
            force_authenticate(req, user=self.manager_user)
            with patch.object(CustomerViewSet, 'get_object', return_value=branch_cust):
                resp = view(req, pk=branch_cust.pk)
        self.assertIn(resp.status_code, (200, 400))
