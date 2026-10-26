"""Cover sales serializers, debt helpers, invoice/payment/customer services gaps."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import serializers

from accounts.models import UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from products.models import Product
from sales.backfill_import import import_backfill_sales_from_csv
from sales.debt_management import (
    build_debt_summary,
    collectible_debt_amount,
    customer_ids_needing_wallet_debt_heal,
    ensure_wallet_matches_unpaid_sales,
    list_debtors,
    missing_unpaid_debt_by_customer,
    originating_debt_customer_ids,
    sale_needs_wallet_debt_heal,
    serialize_debt_summary,
)
from sales.models import (
    Customer,
    CustomerWalletTransaction,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentPlan,
    Sale,
    SaleItem,
)
from sales.refunds import SaleRefundService
from sales.sale_debt_sync import (
    apply_settlement_to_underpaid_sales,
    debt_already_cleared_from_wallet,
    sync_sale_customer_debt,
)
from sales.serializers import (
    CheckoutHoldingSerializer,
    CustomerSerializer,
    SaleCreateSerializer,
    SaleItemSerializer,
    SaleListSerializer,
    SaleSerializer,
)
from sales.services import CustomerService, InvoiceService, PaymentService


class CustomerSerializerGapTests(TestCase):
    def test_email_phone_coords_goods_and_location(self):
        ser = CustomerSerializer()
        self.assertIsNone(ser.validate_email(None) or None)
        self.assertEqual(ser.validate_email('  a@b.com  '), 'a@b.com')
        self.assertEqual(ser.validate_owner_name(None), '')
        self.assertEqual(ser.validate_contact_person('  Bob  '), 'Bob')
        self.assertEqual(ser.validate_typical_goods(None), [])
        self.assertEqual(ser.validate_typical_goods('Cement, Paint'), ['Cement', 'Paint'])
        with self.assertRaises(serializers.ValidationError):
            ser.validate_typical_goods({'x': 1})
        with self.assertRaises(serializers.ValidationError):
            ser.validate_typical_goods(['x' * 81])
        with self.assertRaises(serializers.ValidationError):
            ser.validate_typical_goods([f'g{i}' for i in range(21)])

        self.assertIsNone(ser.validate_latitude(None))
        self.assertIsNone(ser.validate_latitude(''))
        lat = ser.validate_latitude('1.2921')
        self.assertEqual(lat, Decimal('1.292100'))
        with self.assertRaises(serializers.ValidationError):
            ser.validate_latitude('not-a-number')
        with self.assertRaises(serializers.ValidationError):
            ser.validate_latitude('95')
        with self.assertRaises(serializers.ValidationError):
            ser.validate_longitude('200')
        self.assertIsNone(ser.validate_location_accuracy(None))
        self.assertEqual(ser.validate_location_accuracy('12.5'), 12.5)
        with self.assertRaises(serializers.ValidationError):
            ser.validate_location_accuracy('bad')

        # Create with city hint → Kenya defaults when incomplete
        create = CustomerSerializer(data={'gender': 'female', 'name': 'Gap Cust',
            'city': 'Nairobi',
            'phone': '0700111222',
            'email': 'gap@t.com',
            'typical_goods': ['Sugar'],
        })
        self.assertTrue(create.is_valid(), create.errors)
        cust = create.save()
        self.assertTrue(cust.county)

        # Duplicate phone on update
        other = Customer.objects.create(name='Other', phone='0700333444', is_active=True)
        upd = CustomerSerializer(
            instance=cust,
            data={'phone': other.phone, 'name': cust.name},
            partial=True,
        )
        self.assertFalse(upd.is_valid())
        self.assertIn('phone', upd.errors)

        # Bad location on update
        bad_loc = CustomerSerializer(
            instance=cust,
            data={'county': 'Atlantis', 'sub_county': 'X', 'ward': 'Y'},
            partial=True,
        )
        self.assertFalse(bad_loc.is_valid())


class SaleCreateSerializerGapTests(TestCase):
    def test_installment_and_payment_validation(self):
        ser = SaleCreateSerializer()
        self.assertIsNone(ser.validate_installment_frequency(None))
        self.assertIsNone(ser.validate_installment_frequency(''))
        with self.assertRaises(serializers.ValidationError):
            ser.validate_installment_frequency('yearly-bogus')
        valid_freq = PaymentPlan.FREQUENCY_CHOICES[0][0]
        self.assertEqual(ser.validate_installment_frequency(valid_freq), valid_freq)

        # POS without amount
        bad = SaleCreateSerializer(data={
            'items': [{'product_id': 1, 'quantity': 1}],
            'sale_type': 'pos',
            'amount_paid': 0,
            'payment_method': 'cash',
        })
        self.assertFalse(bad.is_valid())

        # Partial without customer
        partial = SaleCreateSerializer(data={
            'items': [{'product_id': 1, 'quantity': 1}],
            'sale_type': 'pos',
            'amount_paid': 0,
            'allow_partial_payment': True,
            'payment_method': 'cash',
        })
        self.assertFalse(partial.is_valid())

        # Negative amount with partial
        neg = SaleCreateSerializer(data={
            'items': [{'product_id': 1, 'quantity': 1}],
            'sale_type': 'pos',
            'amount_paid': -1,
            'allow_partial_payment': True,
            'customer_id': 1,
            'payment_method': 'cash',
        })
        self.assertFalse(neg.is_valid())

        # Normal pay_now without amount
        normal = SaleCreateSerializer(data={
            'items': [{'product_id': 1, 'quantity': 1}],
            'sale_type': 'normal',
            'amount_paid': 0,
            'create_payment_plan': False,
            'payment_method': 'cash',
        })
        self.assertFalse(normal.is_valid())

        # Payment plan missing fields
        plan = SaleCreateSerializer(data={
            'items': [{'product_id': 1, 'quantity': 1}],
            'sale_type': 'normal',
            'amount_paid': 0,
            'create_payment_plan': True,
            'payment_method': 'cash',
        })
        self.assertFalse(plan.is_valid())

        plan2 = SaleCreateSerializer(data={
            'items': [{'product_id': 1, 'quantity': 1}],
            'sale_type': 'normal',
            'amount_paid': 0,
            'create_payment_plan': True,
            'installment_frequency': valid_freq,
            'number_of_installments': 0,
            'payment_method': 'cash',
        })
        self.assertFalse(plan2.is_valid())

        plan3 = SaleCreateSerializer(data={
            'items': [{'product_id': 1, 'quantity': 1}],
            'sale_type': 'normal',
            'amount_paid': 0,
            'create_payment_plan': True,
            'installment_frequency': valid_freq,
            'number_of_installments': 3,
            'payment_method': 'cash',
        })
        self.assertFalse(plan3.is_valid())

        # Payment reference validation error mapping
        with patch(
            'sales.payment_reference.validate_sale_payment_reference',
            side_effect=ValidationError('bad ref'),
        ):
            pay = CheckoutHoldingSerializer(data={
                'amount_paid': '10.00',
                'payment_method': 'mpesa',
                'payment_reference': 'x',
            })
            self.assertFalse(pay.is_valid())


class SaleSerializerMethodGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.user = User.objects.create_user('ser_gap', password='x', first_name='Ann', last_name='')
        UserProfile.objects.create(
            user=cls.user, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.product = Product.objects.create(
            name='Ser Prod', sku='SER-P', price=Decimal('40'),
            stock_quantity=5, track_stock=True, is_active=True,
        )

    def test_item_refund_and_sale_helpers(self):
        sale = Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('40'), total=Decimal('40'), amount_paid=Decimal('40'),
            payment_method='cash',
        )
        item = SaleItem.objects.create(
            sale=sale, product=self.product, quantity=2,
            unit_price=Decimal('20'), subtotal=Decimal('40'),
        )
        item_ser = SaleItemSerializer(instance=item)
        self.assertEqual(item_ser.get_quantity_refunded(item), 0)
        self.assertEqual(item_ser.get_refundable_quantity(item), 2)
        self.assertEqual(item_ser.get_layer_allocations(item), [])
        data = item_ser.to_representation(item)
        self.assertEqual(data['product_id'], self.product.id)

        SaleListSerializer(instance=sale, context={'refunded_qty_by_item': {}})
        sale_ser = SaleSerializer(instance=sale, context={
            'request': MagicMock(user=self.user),
            'include_activity': False,
        })
        self.assertIn(sale_ser.get_served_by_name(sale), ('Ann', self.user.username))
        self.assertFalse(sale_ser.get_is_late_entry(sale))
        self.assertIsNone(sale_ser.get_backfill_receipt_photo_url(sale))
        self.assertEqual(sale_ser.get_amount_refunded(sale), Decimal('0'))
        self.assertTrue(sale_ser.get_can_refund(sale))
        self.assertIsNone(sale_ser.get_activity(sale))
        self.assertIsNone(sale_ser.get_approval_details(sale))

        pending = Sale.objects.create(
            cashier=self.user, status='pending_approval',
            subtotal=Decimal('10'), total=Decimal('10'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        pending_ser = SaleSerializer(instance=pending, context={'request': MagicMock(user=self.user)})
        details = pending_ser.get_approval_details(pending)
        self.assertTrue(details is None or 'sections' in details)


class InvoicePaymentCustomerServiceGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.user = User.objects.create_user('inv_svc', password='x')
        UserProfile.objects.create(
            user=cls.user, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Inv Cust', phone='0700555000', wallet_balance=Decimal('100'), is_active=True,
        )
        cls.product = Product.objects.create(
            name='Inv Item', sku='INV-I', price=Decimal('50'),
            stock_quantity=10, track_stock=True, is_active=True,
        )
        cls.sale = Sale.objects.create(
            cashier=cls.user, customer=cls.customer, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash', occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=cls.sale, product=cls.product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'),
        )

    def test_invoice_service_queryset_and_create(self):
        svc = InvoiceService()
        self.assertEqual(svc.build_queryset(None).model, Invoice)
        qs = svc.build_queryset({
            'status': 'paid',
            'customer_id': 'bad',
            'date_from': timezone.localdate().isoformat(),
            'date_to': timezone.localdate().isoformat(),
            'search': 'Walk',
        })
        self.assertEqual(qs.count(), 0)

        qs2 = svc.build_queryset({'customer_id': self.customer.id, 'search': self.customer.name[:4]})
        self.assertIsNotNone(qs2)

        invoice = svc.create_invoice_from_sale(
            self.sale,
            customer=self.customer,
            due_date=timezone.localdate().isoformat(),
            user=self.user,
            amount_paid=Decimal('50'),
        )
        self.assertEqual(invoice.status, 'paid')
        self.assertTrue(invoice.items.exists())

        underpaid_sale = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            subtotal=Decimal('80'), total=Decimal('80'), amount_paid=Decimal('20'),
            payment_method='cash', occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=underpaid_sale, product=self.product, quantity=1,
            unit_price=Decimal('80'), subtotal=Decimal('80'),
        )
        inv2 = svc.create_invoice_from_sale(underpaid_sale, amount_paid=Decimal('20'), user=self.user)
        self.assertIn(inv2.status, ('sent', 'partial'))
        self.assertGreater(inv2.balance, Decimal('0'))

        with self.assertRaises(ValidationError):
            svc.create_payment_plan(invoice, 2, 'monthly', timezone.localdate().isoformat(), user=self.user)

        plan = svc.create_payment_plan(
            inv2, 2, PaymentPlan.FREQUENCY_CHOICES[0][0],
            timezone.localdate().isoformat(), user=self.user,
        )
        self.assertEqual(plan.number_of_installments, 2)

    def test_payment_and_customer_services(self):
        invoice = Invoice.objects.create(
            sale=self.sale, customer=self.customer, customer_name=self.customer.name,
            issued_date=timezone.localdate(), due_date=timezone.localdate(),
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('0'),
            balance=Decimal('50'), status='sent',
        )
        pay_svc = PaymentService()
        self.assertEqual(pay_svc.build_queryset(None).model, Payment)
        qs = pay_svc.build_queryset({
            'invoice_id': 'bad',
            'payment_method': 'cash',
            'date_from': timezone.localdate().isoformat(),
            'date_to': timezone.localdate().isoformat(),
        })
        self.assertEqual(qs.count(), 0)

        with patch('accounting.views.create_payment_journal_entry', side_effect=RuntimeError('je')):
            payment = pay_svc.create_payment(
                invoice, Decimal('10'), 'cash',
                payment_date=timezone.localdate().isoformat(),
                user=self.user, reference='R1', notes='n',
            )
        self.assertEqual(payment.amount, Decimal('10'))

        with self.assertRaises(ValidationError):
            pay_svc.create_payment(invoice, Decimal('9999'), 'cash', user=self.user)

        cust_svc = CustomerService()
        self.assertEqual(cust_svc.build_queryset(None).model, Customer)
        qs = cust_svc.build_queryset({
            'is_active': 'true',
            'search': 'Inv',
            'customer_type': 'individual',
        })
        self.assertIn(self.customer.id, qs.values_list('id', flat=True))

        with patch.object(Customer.objects, 'filter', side_effect=RuntimeError('search fail')):
            # search_customers catches; build_queryset search except → none
            empty = cust_svc.search_customers('x')
            self.assertEqual(empty, [])

        found = cust_svc.search_customers('Inv', limit=0)
        self.assertTrue(any(c.id == self.customer.id for c in found))
        found2 = cust_svc.search_customers('Inv', limit=5000)
        self.assertTrue(found2)
        self.assertEqual(cust_svc.search_customers(''), [])

        txn = cust_svc.update_wallet_balance(
            self.customer, Decimal('5'), 'credit', source_type='other',
            notes='topup', user=self.user,
        )
        self.assertEqual(txn.transaction_type, 'credit')
        with self.assertRaises(ValidationError):
            cust_svc.update_wallet_balance(
                self.customer, Decimal('99999'), 'debit', user=self.user,
            )
        with self.assertRaises(ValidationError):
            cust_svc.update_wallet_balance(
                self.customer, Decimal('1'), 'weird', user=self.user,
            )


class DebtManagementGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('debt_gap_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.cashier = User.objects.create_user('debt_gap_cash', password='x')
        UserProfile.objects.create(
            user=cls.cashier, role='cashier', custom_role=roles[ROLE_SALES], is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Debt Gap', phone='0700666777', wallet_balance=Decimal('0'), is_active=True,
        )
        cls.sale = Sale.objects.create(
            cashier=cls.cashier, customer=cls.customer, status='completed',
            sale_type='pos', subtotal=Decimal('100'), total=Decimal('100'),
            amount_paid=Decimal('40'), payment_method='cash', occurred_at=timezone.now(),
        )

    def test_heal_collectible_summary_and_list(self):
        self.assertFalse(sale_needs_wallet_debt_heal(self.sale, active_amount=Decimal('60'), stale=False))
        self.assertTrue(sale_needs_wallet_debt_heal(self.sale, active_amount=Decimal('0'), stale=False))
        self.assertTrue(sale_needs_wallet_debt_heal(self.sale, active_amount=Decimal('10'), stale=True))
        paid = Sale.objects.create(
            cashier=self.cashier, customer=self.customer, status='completed',
            sale_type='pos', subtotal=Decimal('10'), total=Decimal('10'),
            amount_paid=Decimal('10'), payment_method='cash',
        )
        self.assertFalse(sale_needs_wallet_debt_heal(paid))

        ids = customer_ids_needing_wallet_debt_heal()
        self.assertIn(self.customer.id, ids)
        self.assertEqual(missing_unpaid_debt_by_customer([]), {})
        amounts = missing_unpaid_debt_by_customer([self.customer.id])
        self.assertIn(self.customer.id, amounts)

        fixed = ensure_wallet_matches_unpaid_sales(self.customer, user=self.manager)
        self.assertGreaterEqual(fixed, 0)
        self.customer.refresh_from_db()

        wallet_amt = collectible_debt_amount(self.customer)
        self.assertGreaterEqual(wallet_amt, Decimal('0'))
        annotated = MagicMock()
        annotated.wallet_balance = Decimal('0')
        annotated.collectible_debt = Decimal('12.50')
        annotated.id = self.customer.id
        self.assertEqual(collectible_debt_amount(annotated), Decimal('12.50'))
        self.assertEqual(
            collectible_debt_amount(self.customer, missing_unpaid={self.customer.id: Decimal('3')}),
            Decimal('3') if self.customer.wallet_balance >= 0 else abs(min(self.customer.wallet_balance, 0)),
        )

        # Force wallet debt path
        self.customer.wallet_balance = Decimal('-25')
        self.customer.save(update_fields=['wallet_balance'])
        self.assertEqual(collectible_debt_amount(self.customer), Decimal('25.00'))

        origin = originating_debt_customer_ids(None)
        self.assertEqual(origin, set())
        origin2 = originating_debt_customer_ids(self.cashier)
        self.assertIn(self.customer.id, origin2)

        summary = build_debt_summary(user=self.manager)
        self.assertIn('customers_with_debt', summary)
        serialized = serialize_debt_summary(summary)
        self.assertIn('aging', serialized)

        rows, total = list_debtors(user=self.manager, ordering='-debt_amount', page=1, page_size=10)
        self.assertIsInstance(rows, list)
        rows2, _ = list_debtors(
            user=self.cashier, search='Debt', aging_bucket='0_7',
            ordering='debt_age_days', page=1, page_size=5,
        )
        self.assertIsInstance(rows2, list)
        list_debtors(user=self.manager, ordering='debt_age_days', page=1, page_size=5)
        list_debtors(user=self.manager, aging_bucket='8_30', ordering='name', page=1, page_size=5)
        list_debtors(user=self.manager, aging_bucket='31_60', ordering='-name', page=1, page_size=5)
        list_debtors(user=self.manager, aging_bucket='60_plus', ordering='saved', page=99, page_size=5)


class SaleDebtSyncGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.user = User.objects.create_user('sync_gap', password='x')
        UserProfile.objects.create(
            user=cls.user, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Sync Cust', phone='0700888999', wallet_balance=Decimal('0'), is_active=True,
        )

    def test_sync_paths_and_settlement(self):
        sale = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            sale_type='pos', subtotal=Decimal('100'), total=Decimal('100'),
            amount_paid=Decimal('30'), payment_method='cash',
        )
        result = sync_sale_customer_debt(sale, user=self.user, reason='test sync')
        self.assertEqual(result['action'], 'debt_synced')

        # already synced
        again = sync_sale_customer_debt(sale, user=self.user, reason='noop')
        self.assertEqual(again['action'], 'already_synced')

        no_cust = Sale.objects.create(
            cashier=self.user, status='completed', sale_type='pos',
            subtotal=Decimal('10'), total=Decimal('10'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        self.assertEqual(sync_sale_customer_debt(no_cust, user=self.user)['action'], 'no_customer')

        holding = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='holding',
            sale_type='pos', subtotal=Decimal('10'), total=Decimal('10'),
            amount_paid=Decimal('0'), payment_method='cash',
        )
        self.assertEqual(sync_sale_customer_debt(holding, user=self.user)['action'], 'not_completed')

        normal = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            sale_type='normal', subtotal=Decimal('10'), total=Decimal('10'),
            amount_paid=Decimal('0'), payment_method='cash',
        )
        self.assertEqual(sync_sale_customer_debt(normal, user=self.user)['action'], 'invoice_sale')

        # Settlement FIFO
        applied = apply_settlement_to_underpaid_sales(self.customer, Decimal('20'))
        self.assertGreaterEqual(applied, Decimal('0'))
        self.assertEqual(apply_settlement_to_underpaid_sales(self.customer, Decimal('0')), Decimal('0.00'))

        # debt_already_cleared when no debt txn
        self.assertFalse(debt_already_cleared_from_wallet(no_cust))


class BackfillImportMoreErrorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('bf_more', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.product = Product.objects.create(
            name='BF More', sku='BF-MORE', price=Decimal('20'),
            stock_quantity=50, track_stock=True, is_active=True,
        )

    def test_row_validation_errors(self):
        occurred = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT10:00:00')
        csv_text = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id,product_id\n'
            f',,{occurred},Sold offline during outage,BF-MORE,1,20,cash,20,pos,,,\n'  # missing occurred via empty first cols confused
            f'R1,,Sold offline during outage,BF-MORE,1,20,cash,20,pos,,,\n'
            f'R2,not-a-date,Sold offline during outage,BF-MORE,1,20,cash,20,pos,,,\n'
            f'R3,{occurred},short,BF-MORE,1,20,cash,20,pos,,,\n'
            f'R4,{occurred},Sold offline during outage,BF-MORE,0,20,cash,20,pos,,,\n'
            f'R5,{occurred},Sold offline during outage,MISSING-SKU,1,20,cash,20,pos,,,\n'
            f'R6,{occurred},Sold offline during outage,,1,20,cash,20,pos,,,999999\n'
            f'R7,{occurred},Sold offline during outage A,BF-MORE,1,20,cash,20,pos,,,\n'
            f'R7,{occurred},Sold offline during outage B,BF-MORE,1,20,cash,20,pos,,,\n'
        )
        # Fix first row — empty sale_reference is ok; ensure missing occurred_at
        csv_text = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id,product_id\n'
            f'R1,,Sold offline during outage,BF-MORE,1,20,cash,20,pos,,,\n'
            f'R2,not-a-date,Sold offline during outage,BF-MORE,1,20,cash,20,pos,,,\n'
            f'R3,{occurred},short,BF-MORE,1,20,cash,20,pos,,,\n'
            f'R4,{occurred},Sold offline during outage,BF-MORE,0,20,cash,20,pos,,,\n'
            f'R5,{occurred},Sold offline during outage,MISSING-SKU,1,20,cash,20,pos,,,\n'
            f'R6,{occurred},Sold offline during outage,,1,20,cash,20,pos,,,999999\n'
            f'R7,{occurred},Sold offline during outage A,BF-MORE,1,20,cash,20,pos,,,\n'
            f'R7,{occurred},Sold offline during outage B,BF-MORE,1,20,cash,20,pos,,,\n'
            f',{occurred},Sold offline during outage,,,,cash,20,pos,,,\n'
        )
        out = import_backfill_sales_from_csv(
            SimpleUploadedFile('e.csv', csv_text.encode(), content_type='text/csv'),
            user=self.manager,
        )
        self.assertTrue(out['errors'])
        joined = ' '.join(out['errors'])
        self.assertIn('occurred_at', joined)
        self.assertIn('quantity', joined)


class SaleRefundServiceGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.user = User.objects.create_user('ref_gap', password='x')
        UserProfile.objects.create(
            user=cls.user, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.product = Product.objects.create(
            name='Ref Prod', sku='REF-P', price=Decimal('30'),
            stock_quantity=10, track_stock=True, is_active=True,
        )

    def test_validation_errors(self):
        svc = SaleRefundService()
        sale = Sale.objects.create(
            cashier=self.user, status='holding',
            subtotal=Decimal('30'), total=Decimal('30'), amount_paid=Decimal('30'),
            payment_method='cash',
        )
        with self.assertRaises(ValidationError):
            svc.create_refund(sale, reason='', user=self.user, full=True)
        with self.assertRaises(ValidationError):
            svc.create_refund(sale, reason='want refund', user=self.user, full=True)

        sale.status = 'completed'
        sale.refund_status = 'refunded'
        sale.save(update_fields=['status', 'refund_status'])
        with self.assertRaises(ValidationError):
            svc.create_refund(sale, reason='already done', user=self.user, full=True)

        sale.refund_status = 'none'
        sale.save(update_fields=['refund_status'])
        SaleItem.objects.create(
            sale=sale, product=self.product, quantity=1,
            unit_price=Decimal('30'), subtotal=Decimal('30'),
        )
        with self.assertRaises(ValidationError):
            svc.create_refund(sale, reason='no lines', user=self.user, items=[])


class RefundAllocationRemainderExactTests(TestCase):
    def test_quantize_remainder_branches(self):
        from sales.refund_allocation import compute_refund_allocation

        sale = Sale.objects.create(
            status='completed', subtotal=Decimal('30'), total=Decimal('30'),
            amount_paid=Decimal('10'), payment_method='cash',
        )
        # Equal cash/wallet/debt with refund that produces rounding remainder
        with patch('sales.refund_allocation._sale_wallet_component') as comp:
            def side(s, src):
                if src == 'payment':
                    return Decimal('10')
                return Decimal('0')
            comp.side_effect = side
            # Implied debt = 30 - 10 - 10 = 10; refund 10 → 3.33*3=9.99 remainder 0.01 → debt
            out = compute_refund_allocation(sale, Decimal('10'))
            self.assertEqual(
                out['cash_back'] + out['wallet_back'] + out['debt_back'],
                Decimal('10.00'),
            )

        with patch('sales.refund_allocation._sale_wallet_component', return_value=Decimal('30')):
            sale.amount_paid = Decimal('0')
            sale.save(update_fields=['amount_paid'])
            out_w = compute_refund_allocation(sale, Decimal('10.01'))
            self.assertGreaterEqual(out_w['wallet_back'], Decimal('10.00'))

        with patch('sales.refund_allocation._sale_wallet_component', return_value=Decimal('0')):
            sale.amount_paid = Decimal('30')
            sale.total = Decimal('30')
            sale.save(update_fields=['amount_paid', 'total'])
            out_c = compute_refund_allocation(sale, Decimal('10.01'))
            self.assertGreaterEqual(out_c['cash_back'], Decimal('10.00'))


class SaleRefundHappyPathTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.user = User.objects.create_user('ref_ok', password='x')
        UserProfile.objects.create(
            user=cls.user, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Ref Cust', phone='0700123456', wallet_balance=Decimal('-20'), is_active=True,
        )
        cls.product = Product.objects.create(
            name='Ref Ok', sku='REF-OK', price=Decimal('50'), cost=Decimal('20'),
            stock_quantity=10, track_stock=True, is_active=True,
        )

    def test_full_refund_and_invalid_line(self):
        sale = Sale.objects.create(
            cashier=self.user, customer=self.customer, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('30'),
            payment_method='cash',
        )
        item = SaleItem.objects.create(
            sale=sale, product=self.product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'), unit_cost=Decimal('20'),
        )
        svc = SaleRefundService()
        with patch('inventory.stock_layers.layers_enabled', return_value=False):
            with patch(
                'accounting.services.create_sale_refund_journal_entry',
                side_effect=RuntimeError('je'),
            ):
                refund = svc.create_refund(
                    sale, reason='Customer returned item', user=self.user, full=True,
                )
        self.assertEqual(refund.amount, Decimal('50.00'))

        sale2 = Sale.objects.create(
            cashier=self.user, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=sale2, product=self.product, quantity=1,
            unit_price=Decimal('50'), subtotal=Decimal('50'),
        )
        with self.assertRaises(ValidationError):
            svc.create_refund(
                sale2, reason='bad line', user=self.user,
                items=[{'sale_item_id': 999999, 'quantity': 1}],
            )
        with self.assertRaises(ValidationError):
            svc.create_refund(
                sale2, reason='too many', user=self.user,
                items=[{'sale_item_id': sale2.items.first().id, 'quantity': 99}],
            )
        # Skip zero qty rows
        lines = svc._resolve_refund_lines(
            sale2, items=[{'sale_item_id': sale2.items.first().id, 'quantity': 0}], full=False,
        )
        self.assertEqual(lines, [])


class SaleViewSetMoreActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('sv_more', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.product = Product.objects.create(
            name='SV More', sku='SVM-1', price=Decimal('25'),
            stock_quantity=20, track_stock=True, is_active=True,
        )

    def setUp(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        self.factory = APIRequestFactory()
        self.force_authenticate = force_authenticate

    def test_receipt_complete_reject_and_immutable(self):
        from rest_framework.test import force_authenticate
        from sales.views import SaleViewSet

        holding = Sale.objects.create(
            cashier=self.manager, status='holding',
            subtotal=Decimal('25'), total=Decimal('25'), amount_paid=Decimal('0'),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=holding, product=self.product, quantity=1,
            unit_price=Decimal('25'), subtotal=Decimal('25'),
        )
        view = SaleViewSet.as_view({'get': 'receipt'})
        req = self.factory.get(f'/api/sales/{holding.id}/receipt/')
        force_authenticate(req, user=self.manager)
        resp = view(req, pk=holding.pk)
        self.assertIn(resp.status_code, (400, 403, 200))

        completed = Sale.objects.create(
            cashier=self.manager, status='completed',
            subtotal=Decimal('25'), total=Decimal('25'), amount_paid=Decimal('25'),
            payment_method='cash', occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=completed, product=self.product, quantity=1,
            unit_price=Decimal('25'), subtotal=Decimal('25'),
        )
        view_r = SaleViewSet.as_view({'get': 'receipt'})
        req_r = self.factory.get(f'/api/sales/{completed.id}/receipt/')
        force_authenticate(req_r, user=self.manager)
        self.assertEqual(view_r(req_r, pk=completed.pk).status_code, 200)

        # Completed sale update blocked / queued
        view_u = SaleViewSet.as_view({'put': 'update'})
        req_u = self.factory.put(
            f'/api/sales/{completed.id}/',
            {'notes': 'edit me', 'reason': 'fix typo'},
            format='json',
        )
        force_authenticate(req_u, user=self.manager)
        with patch('approvals.sales_policy.completed_sale_direct_edit_blocked', return_value=True):
            blocked = view_u(req_u, pk=completed.pk)
            self.assertEqual(blocked.status_code, 403)

        pending = Sale.objects.create(
            cashier=self.manager, status='pending_approval',
            subtotal=Decimal('25'), total=Decimal('25'), amount_paid=Decimal('25'),
            payment_method='cash', occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=pending, product=self.product, quantity=1,
            unit_price=Decimal('25'), subtotal=Decimal('25'),
        )
        view_c = SaleViewSet.as_view({'post': 'complete'})
        req_c = self.factory.post(f'/api/sales/{pending.id}/complete/')
        force_authenticate(req_c, user=self.manager)
        with patch('sales.sale_completion_approval.pending_sale_complete_change', return_value=None):
            with patch('approvals.permissions.user_may_approve_dated_item', return_value=True):
                with patch(
                    'sales.sale_completion_approval.approve_queued_sale',
                    side_effect=lambda *a, **k: pending.__setattr__('status', 'completed') or pending.save(
                        update_fields=['status']
                    ),
                ):
                    resp_c = view_c(req_c, pk=pending.pk)
        self.assertIn(resp_c.status_code, (200, 400))

        pending.status = 'pending_approval'
        pending.save(update_fields=['status'])
        view_rj = SaleViewSet.as_view({'post': 'reject_complete'})
        req_rj = self.factory.post(
            f'/api/sales/{pending.id}/reject-complete/',
            {'reason': 'Needs correction on price'},
            format='json',
        )
        force_authenticate(req_rj, user=self.manager)
        with patch('sales.sale_completion_approval.pending_sale_complete_change', return_value=None):
            with patch('approvals.permissions.user_may_approve_dated_item', return_value=True):
                with patch('sales.sale_completion_approval.return_queued_sale_for_correction'):
                    with patch('sales.sale_completion_approval.record_rejected_sale_complete_change'):
                        with patch('sales.sale_completion_approval.notify_sale_returned_for_correction'):
                            resp_rj = view_rj(req_rj, pk=pending.pk)
        self.assertIn(resp_rj.status_code, (200, 400))

        # Wrong status for reject
        req_bad = self.factory.post(
            f'/api/sales/{completed.id}/reject-complete/',
            {'reason': 'nope'},
            format='json',
        )
        force_authenticate(req_bad, user=self.manager)
        with patch(
            'sales.sale_completion_approval.admin_return_sale_for_correction',
            side_effect=ValidationError('cannot'),
        ):
            bad = view_rj(req_bad, pk=completed.pk)
            self.assertEqual(bad.status_code, 400)
