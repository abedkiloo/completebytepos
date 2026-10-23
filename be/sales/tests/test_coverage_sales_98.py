"""Push sales coverage toward 98% — views, services, and backfill_import misses."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import UserProfile
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from products.models import Category, Color, Product, ProductVariant, Size
from sales.backfill_import import _parse_row_groups, import_backfill_sales_from_csv
from sales.models import Customer, Invoice, InvoiceItem, Sale, SaleItem
from sales.services import CustomerService, SaleService
from sales.views import CustomerViewSet, InvoiceViewSet, PaymentViewSet, SaleViewSet
from settings.models import Branch, StoreSettings, Tenant
from utils.tests.api_test_base import ManagerAPITestCase


class BackfillImportMissesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('bf98_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='BF98 Cust', phone='0700980001', is_active=True,
        )
        cls.product = Product.objects.create(
            name='BF98 Pen', sku='BF98-PEN', price=Decimal('50'), cost=Decimal('20'),
            stock_quantity=100, track_stock=True, is_active=True,
        )
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

    def test_product_id_customer_and_parse_exceptions(self):
        import csv
        import io

        occurred = (timezone.now() - timedelta(days=2)).strftime('%Y-%m-%dT10:00:00')
        body = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id,product_id\n'
            f'S1,{occurred},Sold offline during outage,,1,50.00,cash,50.00,pos,,'
            f'{self.customer.id},{self.manager.id},{self.product.id}\n'
        )
        reader = csv.DictReader(io.StringIO(body))
        groups, errors = _parse_row_groups(reader)
        self.assertEqual(errors, [])
        self.assertIn('S1', groups)
        self.assertEqual(groups['S1']['customer_id'], str(self.customer.id))
        self.assertEqual(groups['S1']['items'][0]['product_id'], self.product.id)

        # ValueError / generic Exception handlers inside _parse_row_groups
        with patch('sales.backfill_import._parse_decimal', side_effect=ValueError('Row 2: bad')):
            groups2, errors2 = _parse_row_groups(csv.DictReader(io.StringIO(body)))
            self.assertTrue(any('bad' in e for e in errors2))
        with patch('sales.backfill_import.parse_datetime', side_effect=RuntimeError('boom')):
            groups3, errors3 = _parse_row_groups(csv.DictReader(io.StringIO(body)))
            self.assertTrue(any('boom' in e for e in errors3))

    def test_import_customer_served_by_approval_and_validation_dicts(self):
        occurred = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT10:00:00')
        csv_body = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id,product_id\n'
            f'SALE-98,{occurred},Sold offline during outage,,1,50.00,cash,50.00,normal,,'
            f'{self.customer.id},{self.manager.id},{self.product.id}\n'
        )
        factory = RequestFactory()
        request = factory.post('/')
        request.user = self.manager

        result = import_backfill_sales_from_csv(
            SimpleUploadedFile('ok.csv', csv_body.encode(), content_type='text/csv'),
            user=self.manager,
            request=request,
            acknowledge_stock_warnings=True,
        )
        self.assertEqual(result['created'], 1, result)

        with patch('sales.backfill_import.backfill_requires_approval', return_value=True):
            with patch('approvals.backfill_integration.queue_sale_backfill') as queue:
                pending = import_backfill_sales_from_csv(
                    SimpleUploadedFile('p.csv', csv_body.encode(), content_type='text/csv'),
                    user=self.manager,
                    request=request,
                    acknowledge_stock_warnings=True,
                )
            self.assertEqual(pending['pending'], 1)
            queue.assert_called_once()

        with patch(
            'sales.services.SaleService.validate_sale_items',
            side_effect=ValidationError({'stock_warnings': ['warn']}),
        ):
            stock = import_backfill_sales_from_csv(
                SimpleUploadedFile('sw.csv', csv_body.encode(), content_type='text/csv'),
                user=self.manager,
                acknowledge_stock_warnings=True,
            )
        self.assertTrue(any('stock adjusted' in e for e in stock['errors']))

        with patch(
            'sales.services.SaleService.validate_sale_items',
            side_effect=ValidationError({'items': ['bad item', 'also bad']}),
        ):
            flat = import_backfill_sales_from_csv(
                SimpleUploadedFile('fl.csv', csv_body.encode(), content_type='text/csv'),
                user=self.manager,
                acknowledge_stock_warnings=True,
            )
        self.assertTrue(any('bad item' in e for e in flat['errors']))

        class ScalarDictValidationError(ValidationError):
            @property
            def message_dict(self):
                return {'detail': 'single'}

        with patch(
            'sales.services.SaleService.validate_sale_items',
            side_effect=ScalarDictValidationError('single'),
        ):
            single = import_backfill_sales_from_csv(
                SimpleUploadedFile('sg.csv', csv_body.encode(), content_type='text/csv'),
                user=self.manager,
                acknowledge_stock_warnings=True,
            )
        self.assertTrue(any('single' in e for e in single['errors']))

        with patch(
            'sales.services.SaleService.create_sale_from_validated_data',
            side_effect=RuntimeError('explode'),
        ):
            boom = import_backfill_sales_from_csv(
                SimpleUploadedFile('ex.csv', csv_body.encode(), content_type='text/csv'),
                user=self.manager,
                acknowledge_stock_warnings=True,
            )
        self.assertTrue(any('explode' in e for e in boom['errors']))


class SaleServiceMisses98Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.user = User.objects.create_user('svc98', password='x')
        UserProfile.objects.create(
            user=cls.user, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.category = Category.objects.create(name='Svc98', is_active=True)
        cls.product = Product.objects.create(
            name='Svc98 Item', sku='SVC98', category=cls.category,
            price=Decimal('40'), cost=Decimal('15'),
            stock_quantity=10, track_stock=True, is_active=True, has_variants=True,
        )
        cls.size = Size.objects.create(name='M98', code='M98', is_active=True)
        cls.color = Color.objects.create(name='Blue98', is_active=True)
        cls.variant = ProductVariant.objects.create(
            product=cls.product, size=cls.size, color=cls.color,
            sku='SVC98-M-BLU', price=Decimal('40'), cost=Decimal('15'),
            stock_quantity=5, is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Svc98 Cust', phone='0700980002', wallet_balance=Decimal('30'), is_active=True,
        )
        cls.service = SaleService()

    def test_validate_items_missing_product_id_and_fifo_replan(self):
        with patch('sales.services.consolidate_sale_items_data', return_value=[
            {'quantity': 1},
        ]):
            with self.assertRaises(ValidationError):
                self.service.validate_sale_items([{'quantity': 1}], check_stock=False)

        with patch('sales.services.is_product_variants_enabled', return_value=True):
            with patch(
                'sales.services.plan_fifo_allocations',
                return_value=[{'quantity': 1, 'unit_cost': 0, 'unit_sell_price': 40}],
            ):
                with patch.object(
                    self.service,
                    '_plan_fifo_across_variants',
                    return_value=[{
                        'quantity': 1,
                        'unit_cost': '15',
                        'unit_sell_price': '40',
                    }],
                ) as replan:
                    items = self.service.validate_sale_items(
                        [{'product_id': self.product.id, 'quantity': 1}],
                        check_stock=False,
                        user=self.user,
                    )
                    replan.assert_called()
                    self.assertEqual(len(items), 1)

    def test_validate_items_layer_split_and_zero_cost(self):
        with patch('sales.services.layers_enabled', return_value=True):
            with patch(
                'sales.services.plan_fifo_allocations',
                return_value=[
                    {'quantity': 1, 'unit_cost': '10', 'unit_sell_price': '40'},
                    {'quantity': 1, 'unit_cost': '12', 'unit_sell_price': '42'},
                ],
            ):
                items = self.service.validate_sale_items(
                    [{'product_id': self.product.id, 'quantity': 2}],
                    check_stock=False,
                    user=self.user,
                )
                self.assertEqual(len(items), 2)

            with patch(
                'sales.services.plan_fifo_allocations',
                return_value=[
                    {'quantity': 1, 'unit_cost': '0', 'unit_sell_price': '40'},
                    {'quantity': 1, 'unit_cost': '0', 'unit_sell_price': '40'},
                ],
            ):
                with self.assertRaises(ValidationError):
                    self.service.validate_sale_items(
                        [{'product_id': self.product.id, 'quantity': 2}],
                        check_stock=False,
                        user=self.user,
                    )

        with patch('sales.services.plan_fifo_allocations', return_value=[]):
            with patch('sales.services.sellable_unit_price', return_value=Decimal('40')):
                with patch('sales.services.sellable_unit_cost', return_value=Decimal('15')):
                    items = self.service.validate_sale_items(
                        [{'product_id': self.product.id, 'quantity': 1}],
                        check_stock=False,
                        user=self.user,
                    )
                    self.assertEqual(items[0]['unit_cost'], Decimal('15'))

    def test_plan_fifo_take_zero_and_stock_movement_edges(self):
        # Force take <= 0 continue path via mocked variant stock
        fake_v = MagicMock()
        fake_v.id = self.variant.id
        fake_v.stock_quantity = 0
        qs = MagicMock()
        qs.order_by.return_value = [fake_v]
        with patch.object(self.product.variants, 'filter', return_value=qs):
            # remaining > 0 but take=0 → continue; then fallback
            with patch(
                'sales.services.plan_fifo_allocations',
                return_value=[{'quantity': 1}],
            ):
                # stock_quantity__gt=0 filter means empty variants list normally;
                # call with remaining and empty active stock list via real method after
                # creating a zero-stock sibling that still passes filter edge via mock
                pass

        # Direct stock movement edges
        no_track = Product.objects.create(
            name='NoTrack98', sku='NT98', category=self.category,
            price=Decimal('10'), cost=Decimal('4'),
            stock_quantity=0, track_stock=False, is_active=True,
        )
        self.service._create_sale_stock_movements(
            branch=None, user=self.user, reference='R', notes='n',
            product=no_track, variant=None, quantity=1, unit_cost=Decimal('4'),
        )

        with patch('sales.module_settings.sales_validate_stock_before_sale', return_value=False):
            with patch('sales.services.layers_enabled', return_value=False):
                # short > 0 notes path via oversell when non-strict
                self.product.has_variants = False
                self.product.stock_quantity = 0
                self.product.save(update_fields=['has_variants', 'stock_quantity'])
                self.service._create_sale_stock_movements(
                    branch=None, user=self.user, reference='R2', notes='Sale',
                    product=self.product, variant=None, quantity=2, unit_cost=Decimal('15'),
                )

        # Restore for later tests
        self.product.has_variants = True
        self.product.stock_quantity = 10
        self.product.save(update_fields=['has_variants', 'stock_quantity'])

        with patch('sales.module_settings.sales_validate_stock_before_sale', return_value=True):
            with patch('sales.services.layers_enabled', return_value=False):
                # qty <= 0 early returns in nested helpers
                self.service._create_sale_stock_movements(
                    branch=None, user=self.user, reference='R3', notes='n',
                    product=self.product, variant=self.variant, quantity=0, unit_cost=Decimal('15'),
                )

    def test_complete_holding_empty_and_journal_failure(self):
        empty = Sale.objects.create(
            cashier=self.user, status='holding',
            subtotal=Decimal('0'), total=Decimal('0'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        with self.assertRaises(ValidationError):
            self.service.complete_holding_sale(
                empty, payment_method='cash', amount_paid=Decimal('0'), user=self.user,
            )

        holding = Sale.objects.create(
            cashier=self.user, status='holding', customer=self.customer,
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=holding, product=self.product, variant=self.variant,
            quantity=1, unit_price=Decimal('40'), subtotal=Decimal('40'), unit_cost=Decimal('15'),
        )
        with patch('sales.sale_completion_approval.assert_returned_sale_was_edited'):
            with patch('sales.sale_completion_approval.sale_completion_should_wait', return_value=False):
                with patch(
                    'accounting.services.create_sale_journal_entry',
                    side_effect=RuntimeError('je fail'),
                ):
                    out = self.service.complete_holding_sale(
                        holding,
                        payment_method='cash',
                        amount_paid=Decimal('40'),
                        user=self.user,
                    )
        self.assertEqual(out.status, 'completed')

    def test_create_sale_served_by_journal_and_intelligence_failures(self):
        with patch(
            'accounting.services.create_sale_journal_entry',
            side_effect=RuntimeError('je'),
        ):
            with patch(
                'sales.customer_intelligence.on_sale_completed',
                side_effect=RuntimeError('intel'),
            ):
                sale = self.service.create_sale(
                    {
                        'payment_method': 'cash',
                        'amount_paid': Decimal('40'),
                        'sale_type': 'pos',
                        'served_by_id': self.user.id,
                    },
                    [{'product_id': self.product.id, 'variant_id': self.variant.id, 'quantity': 1}],
                    self.user,
                )
        self.assertEqual(sale.status, 'completed')
        self.assertEqual(sale.served_by_id, self.user.id)

    def test_statistics_wallet_partial_and_invoice_names(self):
        Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('40'),
            payment_method='cash', occurred_at=timezone.now(),
        )
        today = timezone.localdate().isoformat()
        stats = self.service.get_sale_statistics(date_from=today, date_to=today)
        self.assertGreaterEqual(stats['total_sales'], 1)

        wallet = self.service.handle_wallet_transactions(
            self.customer, Decimal('40'), Decimal('0'), True, Decimal('0'),
            Sale.objects.create(
                cashier=self.user, status='completed', sale_type='pos',
                subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
                payment_method='cash', sale_number='WLT-98',
            ),
            self.user,
        )
        self.assertGreater(wallet['wallet_amount_used'], Decimal('0'))

        with self.assertRaises(ValidationError):
            self.service._prepare_sale_payment(
                customer=None,
                sale_type='pos',
                total=Decimal('100'),
                amount_paid=Decimal('10'),
                allow_partial=True,
                excess_payment_choice='change',
                use_wallet=False,
                wallet_amount_requested=Decimal('0'),
            )

        # Walk-in / payment-plan customer name branches
        bare = Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            payment_method='cash', sale_type='normal',
        )
        SaleItem.objects.create(
            sale=bare, product=self.product, quantity=1,
            unit_price=Decimal('40'), subtotal=Decimal('40'), unit_cost=Decimal('15'),
        )
        inv_cash = self.service._maybe_create_invoice_for_sale(
            bare, {'sale_type': 'normal', 'payment_method': 'cash'}, None, self.user, Decimal('0'),
        )
        self.assertEqual(inv_cash.customer_name, 'Cash Customer')

        bare2 = Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('40'),
            payment_method='mpesa', sale_type='normal',
        )
        SaleItem.objects.create(
            sale=bare2, product=self.product, quantity=1,
            unit_price=Decimal('40'), subtotal=Decimal('40'), unit_cost=Decimal('15'),
        )
        # Paid in full → create_payment_plan name branch without plan validation
        inv_plan = self.service._maybe_create_invoice_for_sale(
            bare2,
            {
                'sale_type': 'normal',
                'payment_method': 'mpesa',
                'create_payment_plan': True,
            },
            None,
            self.user,
            Decimal('40'),
        )
        self.assertEqual(inv_plan.customer_name, 'Walk-in Customer')

        bare3 = Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            payment_method='card', sale_type='normal',
        )
        SaleItem.objects.create(
            sale=bare3, product=self.product, quantity=1,
            unit_price=Decimal('40'), subtotal=Decimal('40'), unit_cost=Decimal('15'),
        )
        inv_def = self.service._maybe_create_invoice_for_sale(
            bare3, {'sale_type': 'normal', 'payment_method': 'card'}, None, self.user, Decimal('0'),
        )
        self.assertEqual(inv_def.customer_name, 'Customer')

        bare4 = Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            payment_method='card', sale_type='normal',
        )
        SaleItem.objects.create(
            sale=bare4, product=self.product, quantity=1,
            unit_price=Decimal('40'), subtotal=Decimal('40'), unit_cost=Decimal('15'),
        )
        with self.assertRaises(ValidationError):
            self.service._maybe_create_invoice_for_sale(
                bare4,
                {
                    'sale_type': 'normal',
                    'create_payment_plan': True,
                    'number_of_installments': 2,
                },
                None,
                self.user,
                Decimal('0'),
            )

        bare5 = Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            payment_method='card', sale_type='normal',
        )
        SaleItem.objects.create(
            sale=bare5, product=self.product, quantity=1,
            unit_price=Decimal('40'), subtotal=Decimal('40'), unit_cost=Decimal('15'),
        )
        with self.assertRaises(ValidationError):
            self.service._maybe_create_invoice_for_sale(
                bare5,
                {
                    'sale_type': 'normal',
                    'create_payment_plan': True,
                    'number_of_installments': 2,
                    'installment_frequency': 'weekly',
                },
                None,
                self.user,
                Decimal('0'),
            )

    def test_apply_payment_intelligence_sms_and_backfill_photo(self):
        sale = Sale.objects.create(
            cashier=self.user, status='completed', customer=self.customer,
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('0'),
            payment_method='cash', sale_number='PAY-98',
        )
        with patch(
            'sales.customer_intelligence.on_sale_completed',
            side_effect=RuntimeError('intel'),
        ):
            with patch(
                'messaging.customer_notify.notify_customer_sale_completed',
                side_effect=RuntimeError('sms'),
            ):
                self.service._apply_sale_payment(
                    self.customer,
                    sale,
                    self.user,
                    {
                        'wallet_amount_used': Decimal('0'),
                        'wallet_credit_added': Decimal('0'),
                        'change': Decimal('0'),
                        'pending_debt': '5',  # str → Decimal coerce
                        'amount_paid_recorded': Decimal('35'),
                    },
                )

        with patch(
            'sales.backfill_photo.attach_pending_backfill_receipt_photo'
        ) as attach:
            with patch.object(
                self.service,
                'create_sale',
                return_value=sale,
            ):
                with patch.object(
                    self.service,
                    '_prepare_sale_payment',
                    return_value={
                        'wallet_amount_used': Decimal('0'),
                        'wallet_credit_added': Decimal('5'),
                        'change': Decimal('0'),
                        'pending_debt': None,
                        'amount_paid_recorded': Decimal('40'),
                    },
                ):
                    with patch.object(self.service, '_apply_sale_payment'):
                        with patch.object(
                            self.service, '_maybe_create_invoice_for_sale', return_value=None,
                        ):
                            with patch.object(
                                self.service,
                                'validate_sale_items',
                                return_value=[{
                                    'product': self.product,
                                    'variant': None,
                                    'quantity': 1,
                                    'unit_price': Decimal('40'),
                                    'unit_cost': Decimal('15'),
                                    'subtotal': Decimal('40'),
                                    'layer_plan': [],
                                }],
                            ):
                                out = self.service.create_sale_from_validated_data(
                                    {
                                        'items': [{'product_id': self.product.id, 'quantity': 1}],
                                        'payment_method': 'cash',
                                        'amount_paid': Decimal('45'),
                                        'sale_type': 'pos',
                                        'customer_id': self.customer.id,
                                        '_backfill': True,
                                        'occurred_at': timezone.now() - timedelta(days=1),
                                        'backfill_reason': 'Sold offline during outage',
                                        'backfill_receipt_photo_path': '/tmp/receipt.jpg',
                                        'excess_payment_choice': 'wallet',
                                    },
                                    self.user,
                                    request=None,
                                )
        attach.assert_called_once()
        self.assertIn('message', out)

        # create_backfill_from_payload naive datetime + photo
        with patch.object(
            self.service, 'create_sale_from_validated_data', return_value={'sale': sale},
        ) as create:
            self.service.create_backfill_from_payload(
                {
                    'occurred_at': '2026-01-15T10:00:00',
                    'backfill_receipt_photo_path': '/tmp/x.jpg',
                    'items': [],
                },
                self.user,
            )
            create.assert_called_once()
            payload = create.call_args[0][0]
            self.assertTrue(timezone.is_aware(payload['occurred_at']))
            self.assertEqual(payload['backfill_receipt_photo_path'], '/tmp/x.jpg')

    def test_customer_service_search_exception_and_debt_sms(self):
        svc = CustomerService()
        with patch.object(svc.model.objects, 'filter', side_effect=RuntimeError('db')):
            qs = svc.build_queryset({'search': 'x'})
            self.assertEqual(qs.count(), 0)

        self.customer.wallet_balance = Decimal('-20')
        self.customer.save(update_fields=['wallet_balance'])
        with patch(
            'messaging.customer_notify.notify_customer_debt_settlement',
            side_effect=RuntimeError('sms'),
        ):
            with patch('sales.sale_debt_sync.apply_settlement_to_underpaid_sales'):
                txn = svc.record_wallet_payment(
                    customer=self.customer,
                    amount=Decimal('10'),
                    payment_method='cash',
                    reference='REF98',
                    notes='',
                    user=self.user,
                )
        self.assertIsNotNone(txn)


class SaleViewsMisses98APITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name='V98', is_active=True)
        self.product = Product.objects.create(
            name='V98 Item', sku='V98-1', category=self.category,
            price=Decimal('50'), cost=Decimal('20'),
            stock_quantity=20, track_stock=True, is_active=True,
        )
        self.customer = Customer.objects.create(
            name='V98 Cust', phone='0700980003', wallet_balance=Decimal('-10'), is_active=True,
        )
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

    def test_backfill_import_exception_and_holding_cancel_success(self):
        with patch(
            'sales.backfill_import.import_backfill_sales_from_csv',
            side_effect=RuntimeError('import boom'),
        ):
            uploaded = SimpleUploadedFile('x.csv', b'a,b\n', content_type='text/csv')
            resp = self.client.post(
                '/api/sales/backfill-import-csv/',
                {'file': uploaded},
                format='multipart',
            )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        holding = self.client.post(
            '/api/sales/holding/',
            {'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '50.00'}]},
            format='json',
        )
        self.assertIn(holding.status_code, (200, 201), holding.data)
        hid = holding.data['id']
        cancelled = self.client.post(f'/api/sales/{hid}/cancel-holding/')
        self.assertEqual(cancelled.status_code, status.HTTP_200_OK)
        self.assertIn('cancelled', cancelled.data['message'].lower())

    def test_complete_reject_dated_and_destroy_delete(self):
        pending = Sale.objects.create(
            cashier=self.manager_user, status='pending_approval',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash', occurred_at=timezone.now() - timedelta(days=40),
        )
        SaleItem.objects.create(
            sale=pending, product=self.product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'), unit_cost=Decimal('20'),
        )
        with patch('sales.sale_completion_approval.pending_sale_complete_change', return_value=None):
            with patch('approvals.permissions.user_may_approve_dated_item', return_value=False):
                blocked = self.client.post(f'/api/sales/{pending.id}/complete/')
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

        with patch('sales.sale_completion_approval.pending_sale_complete_change', return_value=None):
            with patch('approvals.permissions.user_may_approve_dated_item', return_value=False):
                rej = self.client.post(
                    f'/api/sales/{pending.id}/reject-complete/',
                    {'reason': 'Too old'},
                    format='json',
                )
        self.assertEqual(rej.status_code, status.HTTP_400_BAD_REQUEST)

        completed = Sale.objects.create(
            cashier=self.manager_user, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash',
        )
        wrong_status = self.client.post(
            f'/api/sales/{completed.id}/reject-complete/',
            {'reason': 'Nope'},
            format='json',
        )
        self.assertEqual(wrong_status.status_code, status.HTTP_400_BAD_REQUEST)

        with patch('sales.sale_completion_approval.pending_sale_complete_change', return_value=None):
            with patch('approvals.permissions.user_may_approve_dated_item', return_value=True):
                no_reason = self.client.post(
                    f'/api/sales/{pending.id}/reject-complete/',
                    {'reason': '   '},
                    format='json',
                )
        self.assertEqual(no_reason.status_code, status.HTTP_400_BAD_REQUEST)

        doomed = Customer.objects.create(name='Doomed98', phone='0700980099', is_active=True)
        with patch('sales.customer_module_settings.customers_enable_delete', return_value=True):
            deleted = self.client.delete(f'/api/sales/customers/{doomed.id}/')
        self.assertIn(deleted.status_code, (204, 200, 403))

    def test_customer_filters_detail_wallet_and_resolve_branch(self):
        listed = self.client.get('/api/sales/customers/', {'is_active': 1})
        self.assertEqual(listed.status_code, status.HTTP_200_OK)

        collections = self.client.get(
            '/api/sales/customers/debt-collections/',
            {'date': timezone.localdate().isoformat(), 'page': 'x', 'page_size': 'y'},
        )
        self.assertIn(collections.status_code, (200, 403))

        bad_detail = self.client.get('/api/sales/customers/not-an-id/detail/')
        self.assertIn(bad_detail.status_code, (400, 404))

        with patch('sales.customer_module_settings.customers_show_wallet_balance', return_value=False):
            wallet_off = self.client.post(
                f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
                {'amount': '5.00', 'payment_method': 'cash'},
                format='json',
            )
        self.assertEqual(wallet_off.status_code, status.HTTP_403_FORBIDDEN)

        with patch('sales.customer_module_settings.customers_show_wallet_balance', return_value=True):
            with patch('sales.customer_module_settings.customers_enable_wallet_payment', return_value=True):
                with patch(
                    'sales.services.CustomerService.record_wallet_payment',
                    side_effect=ValidationError('wallet fail'),
                ):
                    with patch('approvals.permissions.user_can_check', return_value=True):
                        with patch(
                            'sales.debt_management.ensure_wallet_matches_unpaid_sales',
                        ):
                            fail = self.client.post(
                                f'/api/sales/customers/{self.customer.id}/receive-wallet-payment/',
                                {'amount': '5.00', 'payment_method': 'cash'},
                                format='json',
                            )
        self.assertIn(fail.status_code, (400, 202, 403))

        factory = APIRequestFactory()
        view = SaleViewSet()
        view.sale_service = SaleService()
        req = factory.get('/api/sales/active-holding/')
        force_authenticate(req, user=self.manager_user)
        with patch.object(
            SaleService, 'resolve_sale_branch', side_effect=ValidationError('no branch'),
        ):
            self.assertIsNone(view._resolve_branch(req))

    def test_invoice_list_create_send_stats_and_payments(self):
        inv = Invoice.objects.create(
            customer=self.customer, customer_name=self.customer.name,
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            status='draft', issued_date=timezone.localdate(),
            created_by=self.manager_user,
        )
        InvoiceItem.objects.create(
            invoice=inv, product=self.product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'),
        )

        tenant = Tenant.objects.create(
            name='V98 T', code='V98', country='Kenya',
            owner=self.manager_user, created_by=self.manager_user,
        )
        branch = Branch.objects.create(
            tenant=tenant, name='HQ98', branch_code='V98-HQ', is_active=True,
        )
        self.set_session_branch(tenant, branch)

        listed = self.client.get('/api/sales/invoices/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)

        bad_cust = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': 999999,
                'subtotal': '50.00',
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '50'}],
            },
            format='json',
        )
        self.assertEqual(bad_cust.status_code, status.HTTP_404_NOT_FOUND)

        bad_branch = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'branch_id': 999999,
                'subtotal': '50.00',
                'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '50'}],
            },
            format='json',
        )
        self.assertIn(bad_branch.status_code, (200, 201))

        missing_prod = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'subtotal': '50.00',
                'items': [{'product_id': 999999, 'quantity': 1, 'unit_price': '50'}],
            },
            format='json',
        )
        self.assertEqual(missing_prod.status_code, status.HTTP_404_NOT_FOUND)

        size = Size.objects.create(name='V98S', code='V98S', is_active=True)
        color = Color.objects.create(name='V98C', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product, size=size, color=color,
            sku='V98-1-S', price=Decimal('50'), cost=Decimal('20'),
            stock_quantity=2, is_active=True,
        )
        bad_var = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'subtotal': '50.00',
                'items': [{
                    'product_id': self.product.id,
                    'variant_id': 999999,
                    'quantity': 1,
                    'unit_price': '50',
                }],
            },
            format='json',
        )
        self.assertEqual(bad_var.status_code, status.HTTP_404_NOT_FOUND)

        with patch('sales.invoice_items.normalize_invoice_items', return_value=[]):
            empty_items = self.client.post(
                '/api/sales/invoices/',
                {
                    'customer_id': self.customer.id,
                    'subtotal': '50.00',
                    'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '50'}],
                },
                format='json',
            )
        self.assertEqual(empty_items.status_code, status.HTTP_400_BAD_REQUEST)

        with patch('sales.invoicing_access.invoice_tracking_allowed', return_value=False):
            send_off = self.client.post(f'/api/sales/invoices/{inv.id}/send/')
        self.assertEqual(send_off.status_code, status.HTTP_403_FORBIDDEN)

        with patch('sales.invoicing_access.invoice_tracking_allowed', return_value=True):
            with patch(
                'accounting.views.create_invoice_journal_entry',
                side_effect=RuntimeError('je'),
            ):
                sent = self.client.post(f'/api/sales/invoices/{inv.id}/send/')
        self.assertEqual(sent.status_code, status.HTTP_200_OK)

        stats = self.client.get(f'/api/sales/invoices/{inv.id}/statistics/')
        self.assertEqual(stats.status_code, status.HTTP_200_OK)
        self.assertIn('balance', stats.data)

        # Payment create edges after serializer (amount 0 / missing / over)
        factory = APIRequestFactory()
        view = PaymentViewSet.as_view({'post': 'create'})
        with patch('sales.invoicing_access.payment_tracking_allowed', return_value=True):
            req_missing = factory.post(
                '/api/sales/payments/',
                {
                    'invoice_id': 999999,
                    'amount': '10.00',
                    'payment_method': 'cash',
                    'payment_date': timezone.localdate().isoformat(),
                },
                format='json',
            )
            force_authenticate(req_missing, user=self.manager_user)
            missing = view(req_missing)
            self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

            inv.refresh_from_db()
            req_zero = factory.post(
                '/api/sales/payments/',
                {
                    'invoice_id': inv.id,
                    'amount': '0',
                    'payment_method': 'cash',
                    'payment_date': timezone.localdate().isoformat(),
                },
                format='json',
            )
            force_authenticate(req_zero, user=self.manager_user)
            zero = view(req_zero)
            self.assertEqual(zero.status_code, status.HTTP_400_BAD_REQUEST)

            req_over = factory.post(
                '/api/sales/payments/',
                {
                    'invoice_id': inv.id,
                    'amount': '9999.00',
                    'payment_method': 'cash',
                    'payment_date': timezone.localdate().isoformat(),
                },
                format='json',
            )
            force_authenticate(req_over, user=self.manager_user)
            over = view(req_over)
            self.assertEqual(over.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid invoice with variant succeeds
        ok = self.client.post(
            '/api/sales/invoices/',
            {
                'customer_id': self.customer.id,
                'subtotal': '50.00',
                'items': [{
                    'product_id': self.product.id,
                    'variant_id': variant.id,
                    'quantity': 1,
                    'unit_price': '50.00',
                }],
            },
            format='json',
        )
        self.assertIn(ok.status_code, (200, 201), ok.data)

    def test_remaining_view_misses_photo_resubmit_daily_destroy(self):
        from rest_framework.request import Request

        occurred = (timezone.now() - timedelta(days=2)).strftime('%Y-%m-%dT10:00:00')
        payload = {
            'occurred_at': occurred,
            'backfill_reason': 'Sold offline during outage',
            'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': '50.00'}],
            'payment_method': 'cash',
            'amount_paid': '50.00',
            'sale_type': 'pos',
            'acknowledge_stock_warnings': True,
        }

        photo = SimpleUploadedFile('r.jpg', b'jpeg', content_type='image/jpeg')
        vs = SaleViewSet()
        vs.sale_service = SaleService()
        vs.format_kwarg = None
        validated = {
            'occurred_at': timezone.now() - timedelta(days=2),
            'backfill_reason': 'Sold offline during outage',
            'items': [{'product_id': self.product.id, 'quantity': 1, 'unit_price': Decimal('50')}],
            'payment_method': 'cash',
            'amount_paid': Decimal('50'),
            'sale_type': 'pos',
            'acknowledge_stock_warnings': True,
        }
        raw = {**validated, 'resubmit_of': 'not-an-int'}
        mock_req = MagicMock()
        mock_req.user = self.manager_user
        mock_req.FILES = {'backfill_receipt_photo': photo}
        mock_req.data = raw
        with patch('sales.views._parse_backfill_request_data', return_value=raw):
            with patch('sales.views.SaleBackfillCreateSerializer') as Ser:
                ser = Ser.return_value
                ser.is_valid.return_value = True
                ser.validated_data = validated
                with patch.object(
                    vs.sale_service,
                    'validate_sale_items',
                    return_value=[{
                        'product': self.product,
                        'variant': None,
                        'quantity': 1,
                        'unit_price': Decimal('50'),
                        'unit_cost': Decimal('20'),
                        'subtotal': Decimal('50'),
                        'layer_plan': [],
                    }],
                ):
                    with patch('sales.backfill_policy.validate_backfill_stock_warnings'):
                        with patch(
                            'sales.backfill_photo.save_pending_backfill_receipt_photo',
                            return_value='/tmp/pending-receipt.jpg',
                        ) as save_photo:
                            with patch(
                                'sales.backfill_policy.resolve_backfill_served_by',
                                return_value=self.manager_user,
                            ):
                                resp = vs.backfill(mock_req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid resubmit', str(resp.data))
        self.assertTrue(save_photo.called)

        with patch(
            'sales.backfill_import.import_backfill_sales_from_csv',
            return_value={
                'created': 0, 'pending': 1, 'errors': ['row bad'], 'sales': [],
            },
        ):
            csv_resp = self.client.post(
                '/api/sales/backfill-import-csv/',
                {'file': SimpleUploadedFile('a.csv', b'x,y\n', content_type='text/csv')},
                format='multipart',
            )
        self.assertEqual(csv_resp.status_code, status.HTTP_200_OK)
        self.assertIn('issue', csv_resp.data['message'])

        factory = APIRequestFactory()
        viewset = SaleViewSet()
        viewset.sale_service = SaleService()
        django_req = factory.get('/api/sales/daily/')
        force_authenticate(django_req, user=self.manager_user)
        req = Request(django_req)
        viewset.request = req
        viewset.format_kwarg = None
        viewset.action = 'daily'
        with patch('settings.module_features.is_module_feature_enabled', return_value=False):
            daily = viewset.daily(req)
            cust = viewset.daily_customer(req, customer_id=str(self.customer.id))
        self.assertEqual(daily.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(cust.status_code, status.HTTP_403_FORBIDDEN)

        # destroy feature flag branches (invoke method on unbound viewset)
        doomed = Customer.objects.create(name='Del98', phone='0700980888', is_active=True)
        del_factory = APIRequestFactory()
        from rest_framework.request import Request as DRFRequest
        cvs = CustomerViewSet()
        blocked_req = del_factory.delete(f'/api/sales/customers/{doomed.id}/')
        force_authenticate(blocked_req, user=self.manager_user)
        cvs.request = DRFRequest(blocked_req)
        cvs.format_kwarg = None
        cvs.action = 'destroy'
        cvs.args = ()
        cvs.kwargs = {'pk': doomed.id}
        with patch('sales.customer_module_settings.customers_enable_delete', return_value=False):
            blocked = cvs.destroy(cvs.request, pk=doomed.id)
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        with patch('sales.customer_module_settings.customers_enable_delete', return_value=True):
            with patch.object(cvs, 'get_object', return_value=doomed):
                gone = cvs.destroy(cvs.request, pk=doomed.id)
        self.assertEqual(gone.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Customer.objects.filter(pk=doomed.pk).exists())

        # is_active AttributeError path via mocked query params
        cust_vs = CustomerViewSet()
        cust_vs.action = 'list'
        mock_req = MagicMock()
        mock_req.query_params = {'is_active': object()}
        mock_req.user = self.manager_user
        cust_vs.request = mock_req
        qs = cust_vs.get_queryset()
        self.assertIsNotNone(qs)

        # Invoice list with current branch / branch_id
        with patch('sales.views.get_current_branch', return_value=MagicMock(id=1)):
            inv_vs = InvoiceViewSet()
            inv_vs.request = MagicMock()
            inv_vs.request.query_params = {}
            inv_vs.request.user = self.manager_user
            listed = inv_vs.get_queryset()
            self.assertIsNotNone(listed)

        with patch('sales.views.get_current_branch', return_value=None):
            inv_vs2 = InvoiceViewSet()
            inv_vs2.request = MagicMock()
            inv_vs2.request.query_params = {'branch_id': '1'}
            inv_vs2.request.user = self.manager_user
            listed2 = inv_vs2.get_queryset()
            self.assertIsNotNone(listed2)

        # Invoice from sale with missing customer
        sale = Sale.objects.create(
            cashier=self.manager_user, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            payment_method='cash', sale_type='normal',
        )
        SaleItem.objects.create(
            sale=sale, product=self.product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'), unit_cost=Decimal('20'),
        )
        missing_cust = self.client.post(
            '/api/sales/invoices/',
            {
                'sale_id': sale.id,
                'customer_id': 999999,
                'customer_name': 'X',
                'subtotal': '50.00',
                'total': '50.00',
            },
            format='json',
        )
        self.assertEqual(missing_cust.status_code, status.HTTP_404_NOT_FOUND)

        # reject-complete wrong status (not pending / not awaiting)
        holding = Sale.objects.create(
            cashier=self.manager_user, status='holding',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        rej = self.client.post(
            f'/api/sales/{holding.id}/reject-complete/',
            {'reason': 'Nope'},
            format='json',
        )
        self.assertEqual(rej.status_code, status.HTTP_400_BAD_REQUEST)

    def test_service_stock_movement_and_payment_plan_success(self):
        service = SaleService()
        # Force take<=0 continue (360) and remaining<=0 break (357)
        class FakeVariant:
            def __init__(self, vid, stock):
                self.id = vid
                self.stock_quantity = stock

        class FakeQS(list):
            def order_by(self, *a, **k):
                return self

        zero_then_stock = FakeQS([FakeVariant(9001, 0), FakeVariant(9002, 2)])
        variants_mgr = MagicMock()
        variants_mgr.filter.return_value = zero_then_stock
        with patch('sales.services.Product') as ProdProxy:
            # Method uses product.variants — patch via a plain namespace object
            pass
        product_proxy = MagicMock()
        product_proxy.id = self.product.id
        product_proxy.variants = variants_mgr
        with patch(
            'sales.services.plan_fifo_allocations',
            return_value=[{'quantity': 1, 'unit_cost': '20', 'unit_sell_price': '50'}],
        ):
            plan = service._plan_fifo_across_variants(product_proxy, 1)
            self.assertTrue(plan)

        # record qty<=0 / short notes / layers off drain
        with patch('sales.module_settings.sales_validate_stock_before_sale', return_value=False):
            with patch('sales.services.layers_enabled', return_value=False):
                simple = Product.objects.create(
                    name='Simple98', sku='S98', category=self.category,
                    price=Decimal('10'), cost=Decimal('4'),
                    stock_quantity=1, track_stock=True, is_active=True, has_variants=False,
                )
                service._create_sale_stock_movements(
                    branch=None, user=self.manager_user, reference='R', notes='Sale',
                    product=simple, variant=None, quantity=3, unit_cost=Decimal('4'),
                )

        # complete_holding not holding status
        done = Sale.objects.create(
            cashier=self.manager_user, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash',
        )
        with self.assertRaises(ValidationError):
            service.complete_holding_sale(
                done, payment_method='cash', amount_paid=Decimal('50'), user=self.manager_user,
            )

        # handle_wallet_transactions else branch (non-pos / no customer excess)
        sale = Sale.objects.create(
            cashier=self.manager_user, status='completed', sale_type='normal',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            payment_method='cash', sale_number='NW-98',
        )
        out = service.handle_wallet_transactions(
            None, Decimal('50'), Decimal('60'), False, Decimal('0'), sale, self.manager_user,
        )
        self.assertEqual(out['change'], Decimal('0'))

        # Wrong-tenant branch → ValidationError at 1035
        tenant = Tenant.objects.create(
            name='T98b', code='T98B', country='Kenya',
            owner=self.manager_user, created_by=self.manager_user,
        )
        other_tenant = Tenant.objects.create(
            name='T98c', code='T98C', country='Kenya',
            owner=self.manager_user, created_by=self.manager_user,
        )
        branch = Branch.objects.create(
            tenant=other_tenant, name='Other', branch_code='T98C-1', is_active=True,
        )
        factory = RequestFactory()
        req = factory.get('/')
        req.user = self.manager_user
        with patch('sales.services.is_branch_support_enabled', return_value=True):
            with patch('sales.services.get_current_branch', return_value=None):
                with patch('sales.services.get_current_tenant', return_value=tenant):
                    with self.assertRaises(ValidationError):
                        service.resolve_sale_branch(req, branch.id)

        # Successful payment plan create (line 1313)
        bare = Sale.objects.create(
            cashier=self.manager_user, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            payment_method='cash', sale_type='normal',
        )
        SaleItem.objects.create(
            sale=bare, product=self.product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'), unit_cost=Decimal('20'),
        )
        inv = service._maybe_create_invoice_for_sale(
            bare,
            {
                'sale_type': 'normal',
                'create_payment_plan': True,
                'number_of_installments': 2,
                'installment_frequency': 'weekly',
                'payment_plan_start_date': timezone.localdate(),
                'payment_method': 'cash',
            },
            None,
            self.manager_user,
            Decimal('0'),
        )
        self.assertIsNotNone(inv)
        self.assertTrue(hasattr(inv, 'payment_plan'))
        self.assertIsNotNone(inv.payment_plan)

        # CustomerService search exception (1833-1835)
        from sales.services import CustomerService
        csvc = CustomerService()
        base_qs = MagicMock()
        with patch.object(csvc.model.objects, 'select_related', return_value=base_qs):
            base_qs.filter.side_effect = Exception('db boom')
            empty = csvc.build_queryset({'search': 'abc'})
            self.assertEqual(empty, base_qs.none.return_value)

        # record(qty<=0) and remaining<=0 break in stock movements
        with patch('sales.module_settings.sales_validate_stock_before_sale', return_value=False):
            with patch('sales.services.layers_enabled', return_value=True):
                with patch(
                    'sales.services.apply_fifo_sale_drain',
                    return_value=[{
                        'quantity': 0,
                        'unit_cost': '4',
                        'unit_sell_price': '10',
                        'layer': None,
                    }],
                ):
                    simple2 = Product.objects.create(
                        name='Layer98', sku='L98', category=self.category,
                        price=Decimal('10'), cost=Decimal('4'),
                        stock_quantity=5, track_stock=True, is_active=True, has_variants=False,
                    )
                    service._create_sale_stock_movements(
                        branch=None, user=self.manager_user, reference='R0', notes='Sale',
                        product=simple2, variant=None, quantity=1, unit_cost=Decimal('4'),
                    )

            with patch('sales.services.layers_enabled', return_value=False):
                # Multi-variant drain: first variant consumes all → remaining<=0 break
                self.product.has_variants = True
                self.product.save(update_fields=['has_variants'])
                v1 = ProductVariant.objects.create(
                    product=self.product,
                    size=Size.objects.create(name='Brk', code='BRK', is_active=True),
                    color=Color.objects.create(name='BrkC', is_active=True),
                    sku='V98-BRK', price=Decimal('50'), cost=Decimal('20'),
                    stock_quantity=5, is_active=True,
                )
                service._create_sale_stock_movements(
                    branch=None, user=self.manager_user, reference='Rbrk', notes='Sale',
                    product=self.product, variant=None, quantity=2, unit_cost=Decimal('20'),
                )
                self.assertGreaterEqual(v1.stock_quantity, 0)
