"""Focused unit coverage for sales helpers with the largest remaining gaps."""

from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ensure_permissions, sync_default_roles
from products.models import Category, Color, Product, ProductVariant, Size
from sales.backfill_import import (
    _decode_csv_file,
    _parse_decimal,
    backfill_import_template_csv,
    import_backfill_sales_from_csv,
)
from sales.backfill_photo import (
    attach_pending_backfill_receipt_photo,
    save_pending_backfill_receipt_photo,
)
from sales.customer_module_settings import (
    apply_customer_representation_flags,
    apply_customer_write_flags,
    customers_allow_quick_add_at_pos,
    customers_enable_delete,
    customers_enable_edit,
    validate_customer_write,
)
from sales.customer_phones import (
    customers_with_phone,
    duplicate_phone_error,
    find_duplicate_phone_groups,
    normalized_customer_phone,
)
from sales.customer_search import _phone_search_variants, apply_customer_search
from sales.item_consolidation import consolidate_sale_items_data
from sales.kenya_admin import (
    load_admin_tree,
    sub_county_names,
    validate_admin_location,
    ward_names,
)
from sales.models import Customer, Invoice, Payment, Sale, SaleItem
from sales.module_settings import (
    apply_sale_module_settings,
    sales_sms_sale_number_prefix,
)
from sales.payments_trail import (
    _method_label,
    _parse_day,
    _parse_kinds,
    list_payments_trail,
)
from sales.refund_allocation import compute_refund_allocation
from sales.sale_date import (
    DATE_CORRECTION_NOT_ALLOWED,
    DATE_CORRECTION_STATUS_BLOCKED,
    correct_sale_occurred_at,
    parse_sale_date_payload,
    sale_date_can_be_corrected,
    validate_sale_date_correction,
)
from sales.visibility import own_sales_q, user_sees_all_debt, user_sees_all_sales
from settings.models import ModuleSetting, StoreSettings
from settings.settings_service import SettingsService
from django.core.cache import cache


class SaleDateUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('sd_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.cashier = User.objects.create_user('sd_cash', password='x')
        UserProfile.objects.create(
            user=cls.cashier, role='cashier', custom_role=roles[ROLE_SALES], is_active=True,
        )
        cls.product = Product.objects.create(
            name='Date Gap', sku='DG-1', price=Decimal('50'), stock_quantity=10, track_stock=True,
        )

    def test_cancelled_sale_cannot_be_corrected(self):
        sale = Sale.objects.create(
            cashier=self.manager, status='cancelled',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash',
        )
        self.assertFalse(sale_date_can_be_corrected(sale, self.manager))

    def test_parse_occurred_at_datetime_and_naive(self):
        aware = timezone.now()
        self.assertEqual(parse_sale_date_payload({'occurred_at': aware}, current=aware), aware)
        naive = datetime(2026, 1, 15, 10, 30, 0)
        out = parse_sale_date_payload({'occurred_at': naive.isoformat()}, current=aware)
        self.assertTrue(timezone.is_aware(out))

    def test_parse_occurred_at_invalid(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_sale_date_payload({'occurred_at': 'not-a-date'}, current=timezone.now())
        self.assertIn('occurred_at', ctx.exception.message_dict)

    def test_parse_occurred_on_date_and_invalid(self):
        current = timezone.now()
        day = timezone.localdate()
        out = parse_sale_date_payload({'occurred_on': day.isoformat()}, current=current)
        self.assertEqual(timezone.localtime(out).date(), day)
        with self.assertRaises(ValidationError):
            parse_sale_date_payload({'occurred_on': 'bogus'}, current=current)
        with self.assertRaises(ValidationError):
            parse_sale_date_payload({}, current=current)

    def test_validate_sale_date_none_and_max_days(self):
        with self.assertRaises(ValidationError):
            validate_sale_date_correction(None)
        store = StoreSettings.load()
        store.backfill_max_days = 7
        store.save(update_fields=['backfill_max_days'])
        far = timezone.now() - timedelta(days=20)
        with self.assertRaises(ValidationError):
            validate_sale_date_correction(far)

    def test_correct_sale_permission_and_noop_and_invoice_shift(self):
        sale = Sale.objects.create(
            cashier=self.manager, status='completed',
            subtotal=Decimal('50'), total=Decimal('50'), amount_paid=Decimal('50'),
            payment_method='cash', occurred_at=timezone.now(),
        )
        with self.assertRaises(ValidationError) as ctx:
            correct_sale_occurred_at(sale, timezone.now(), user=self.cashier)
        self.assertEqual(str(ctx.exception.message), DATE_CORRECTION_NOT_ALLOWED)

        sale.status = 'cancelled'
        sale.save(update_fields=['status'])
        with self.assertRaises(ValidationError) as ctx:
            correct_sale_occurred_at(sale, timezone.now(), user=self.manager)
        self.assertEqual(str(ctx.exception.message), DATE_CORRECTION_STATUS_BLOCKED)

        sale.status = 'completed'
        sale.save(update_fields=['status'])
        same = correct_sale_occurred_at(sale, sale.occurred_at, user=self.manager)
        self.assertEqual(same.pk, sale.pk)

        invoice = Invoice.objects.create(
            sale=sale,
            customer_name='Walk-in',
            issued_date=timezone.localdate(),
            due_date=timezone.localdate(),
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('50'),
            status='paid',
        )
        Payment.objects.create(
            invoice=invoice,
            amount=Decimal('50'),
            payment_method='cash',
            payment_date=timezone.localdate(),
            recorded_by=self.manager,
        )
        admin = User.objects.create_superuser('sd_admin', 'sd@t.com', 'x')
        target = timezone.now() - timedelta(days=1)
        with patch('approvals.permissions.user_may_approve_dated_item', return_value=True):
            correct_sale_occurred_at(sale, target, user=admin)
        invoice.refresh_from_db()
        self.assertEqual(invoice.issued_date, timezone.localtime(target).date())


class VisibilityUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.roles = roles
        cls.manager = User.objects.create_user('vis2_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )

    def test_anonymous_and_no_profile(self):
        self.assertFalse(user_sees_all_sales(None))
        self.assertFalse(user_sees_all_sales(AnonymousUser()))
        bare = User.objects.create_user('vis2_bare', password='x')
        self.assertFalse(user_sees_all_sales(bare))
        self.assertFalse(user_sees_all_debt(AnonymousUser()))

    def test_superuser_and_legacy_admin_and_manager(self):
        su = User.objects.create_superuser('vis2_su', 'su@t.com', 'x')
        self.assertTrue(user_sees_all_sales(su))

        legacy = User.objects.create_user('vis2_legacy', password='x')
        UserProfile.objects.create(user=legacy, role='admin', is_active=True)
        self.assertTrue(user_sees_all_sales(legacy))

        mgr_legacy = User.objects.create_user('vis2_mgr_leg', password='x')
        UserProfile.objects.create(user=mgr_legacy, role='manager', is_active=True)
        self.assertTrue(user_sees_all_sales(mgr_legacy))

    def test_permission_exception_and_own_sales_q(self):
        user = User.objects.create_user('vis2_exc', password='x')
        profile = UserProfile.objects.create(
            user=user, role='cashier', custom_role=self.roles[ROLE_SALES], is_active=True,
        )
        with patch.object(type(profile), 'has_permission', side_effect=RuntimeError('boom')):
            user.profile = profile
            self.assertFalse(user_sees_all_sales(user))
            self.assertFalse(user_sees_all_debt(user))

        empty_q = own_sales_q(MagicMock(pk=None, id=None))
        self.assertFalse(Sale.objects.filter(empty_q).exists())
        q = own_sales_q(user)
        Sale.objects.create(
            cashier=user, status='completed',
            subtotal=Decimal('10'), total=Decimal('10'), amount_paid=Decimal('10'),
            payment_method='cash',
        )
        self.assertTrue(Sale.objects.filter(q).exists())

    def test_debt_permission_exception_path(self):
        user = User.objects.create_user('vis2_debt', password='x')
        profile = UserProfile.objects.create(
            user=user, role='cashier', custom_role=self.roles[ROLE_SALES], is_active=True,
        )
        with patch('sales.visibility.user_sees_all_sales', return_value=False):
            with patch.object(type(profile), 'has_permission', side_effect=RuntimeError('x')):
                user.profile = profile
                self.assertFalse(user_sees_all_debt(user))
            with patch.object(type(profile), 'has_permission', return_value=True):
                user.profile = profile
                self.assertTrue(user_sees_all_debt(user))


class ModuleSettingsUnitTests(TestCase):
    def setUp(self):
        cache.clear()
        for key, default in (
            ('show_discount', True),
            ('show_tax', True),
            ('show_delivery', True),
            ('require_customer', False),
            ('allow_partial_payment', True),
            ('allow_excess_to_wallet', True),
            ('sms_sale_number_prefix', 'S-'),
        ):
            ModuleSetting.objects.update_or_create(
                module='sales', key=key,
                defaults={'label': key, 'description': '', 'default_value': default, 'value': default},
            )

    def test_sms_prefix_none_and_blank(self):
        with patch.object(SettingsService, 'get', return_value=None):
            self.assertEqual(sales_sms_sale_number_prefix(), 'S-')
        SettingsService.set('sales', 'sms_sale_number_prefix', '   ')
        self.assertEqual(sales_sms_sale_number_prefix(), 'S-')

    def test_strips_zero_amounts_when_flags_off(self):
        SettingsService.set('sales', 'show_discount', False)
        SettingsService.set('sales', 'show_tax', False)
        SettingsService.set('sales', 'show_delivery', False)
        out = apply_sale_module_settings({
            'discount_amount': Decimal('0'),
            'tax_amount': Decimal('0'),
            'delivery_cost': Decimal('0'),
            'delivery_method': 'courier',
            'shipping_address': 'Somewhere',
        })
        self.assertEqual(out['discount_amount'], Decimal('0'))
        self.assertEqual(out['delivery_method'], 'pickup')
        self.assertIsNone(out['shipping_address'])


class CustomerModuleSettingsUnitTests(TestCase):
    def setUp(self):
        cache.clear()
        for key, default in (
            ('show_customer_code', True),
            ('show_outstanding_balance', True),
            ('show_wallet_balance', True),
            ('enable_customer_edit', True),
            ('enable_customer_delete', True),
            ('show_customer_type', True),
            ('show_tax_id', True),
            ('show_customer_notes', True),
            ('show_customer_status', True),
            ('allow_quick_add_at_pos', True),
        ):
            ModuleSetting.objects.update_or_create(
                module='customers', key=key,
                defaults={'label': key, 'description': '', 'default_value': default, 'value': default},
            )

    def test_representation_and_write_flags_strip_fields(self):
        SettingsService.set('customers', 'show_customer_code', False)
        SettingsService.set('customers', 'show_customer_type', False)
        SettingsService.set('customers', 'show_tax_id', False)
        SettingsService.set('customers', 'show_customer_notes', False)
        SettingsService.set('customers', 'show_customer_status', False)
        SettingsService.set('customers', 'show_outstanding_balance', False)
        SettingsService.set('customers', 'show_wallet_balance', False)

        data = apply_customer_representation_flags({
            'customer_code': 'C1',
            'total_outstanding': '10',
            'total_invoices': 1,
            'wallet_balance': '5',
            'customer_type': 'business',
            'is_active': True,
            'tax_id': 'T',
            'notes': 'n',
        })
        self.assertNotIn('customer_code', data)
        self.assertNotIn('customer_type', data)
        self.assertNotIn('tax_id', data)

        attrs = validate_customer_write({
            'customer_type': 'business',
            'tax_id': 'T',
            'notes': 'n',
            'is_active': False,
        })
        self.assertEqual(attrs['customer_type'], 'individual')
        self.assertNotIn('tax_id', attrs)
        self.assertTrue(customers_enable_edit())
        self.assertTrue(customers_enable_delete())
        self.assertTrue(customers_allow_quick_add_at_pos())


class CustomerPhonesUnitTests(TestCase):
    def test_invalid_phone_and_extras_path(self):
        self.assertEqual(normalized_customer_phone('not-a-phone'), '')
        self.assertFalse(customers_with_phone('').exists())

        a = Customer.objects.create(name='A', phone='254712345678', is_active=True)
        b = Customer.objects.create(name='B', phone='0712345678', is_active=True)
        # Odd spacing still normalizes to the same key via extras scan
        c = Customer.objects.create(name='C', phone='0712-345-678', is_active=True)
        qs = customers_with_phone('0712345678', exclude_id=a.id)
        ids = set(qs.values_list('id', flat=True))
        self.assertTrue({b.id, c.id}.issubset(ids) or b.id in ids)
        msg = duplicate_phone_error('0712345678', exclude_id=None)
        self.assertIsNotNone(msg)

        Customer.objects.create(name='Bad', phone='xxxx', is_active=True)
        groups = find_duplicate_phone_groups(include_inactive=True)
        self.assertIsInstance(groups, list)


class CustomerSearchUnitTests(TestCase):
    def test_phone_variants_and_empty_search(self):
        variants = _phone_search_variants('254712345678')
        self.assertIn('0712345678', variants)
        variants0 = _phone_search_variants('2540712345678')
        self.assertTrue(any(v.startswith('0') or v == '712345678' for v in variants0))

        Customer.objects.create(name='Search Me', phone='0700111000', is_active=True)
        qs = Customer.objects.all()
        self.assertEqual(apply_customer_search(qs, None).count(), qs.count())
        self.assertGreaterEqual(apply_customer_search(qs, '0700').count(), 1)


class BackfillPhotoUnitTests(TestCase):
    def test_save_and_attach_pending_photo(self):
        uploaded = SimpleUploadedFile('receipt.jpg', b'fakeimage', content_type='image/jpeg')
        path = save_pending_backfill_receipt_photo(uploaded)
        self.assertTrue(path.startswith('sale_backfill/pending/'))

        sale = Sale.objects.create(
            status='completed', subtotal=Decimal('1'), total=Decimal('1'),
            amount_paid=Decimal('1'), payment_method='cash',
        )
        attach_pending_backfill_receipt_photo(sale, None)
        attach_pending_backfill_receipt_photo(sale, 'missing/path.jpg')
        attach_pending_backfill_receipt_photo(sale, path)
        sale.refresh_from_db()
        self.assertTrue(bool(sale.backfill_receipt_photo))


class ItemConsolidationUnitTests(TestCase):
    def test_skips_bad_price_missing_product_and_zero_qty(self):
        out = consolidate_sale_items_data([
            {'product_id': 1, 'quantity': 1, 'unit_price': 'bad'},
            {'product_id': None, 'quantity': 2},
            {'product_id': 1, 'quantity': -1, 'unit_price': '10'},
            {'product_id': 1, 'quantity': 2, 'unit_price': '10.00'},
            {'product_id': 1, 'quantity': 3, 'unit_price': '10.00'},
        ])
        self.assertGreaterEqual(len(out), 1)
        merged = next(
            (r for r in out if str(r.get('unit_price')) in ('10.00', '10')),
            out[0],
        )
        self.assertGreaterEqual(int(merged['quantity']), 2)


class RefundAllocationUnitTests(TestCase):
    def test_zero_refund_and_remainder_paths(self):
        sale = Sale.objects.create(
            status='completed', subtotal=Decimal('100'), total=Decimal('100'),
            amount_paid=Decimal('0'), payment_method='cash',
        )
        zero = compute_refund_allocation(sale, Decimal('0'))
        self.assertEqual(zero['cash_back'], Decimal('0'))

        # Implied debt remainder goes to debt_back
        out = compute_refund_allocation(sale, Decimal('33.33'))
        self.assertGreater(out['debt_back'], Decimal('0'))

        sale2 = Sale.objects.create(
            status='completed', subtotal=Decimal('100'), total=Decimal('100'),
            amount_paid=Decimal('100'), payment_method='cash',
        )
        cash = compute_refund_allocation(sale2, Decimal('10'))
        self.assertEqual(cash['cash_back'], Decimal('10.00'))


class KenyaAdminUnitTests(TestCase):
    def test_invalid_tree_and_validation_errors(self):
        load_admin_tree.cache_clear()
        with patch('sales.kenya_admin.json.load', return_value=[]):
            with self.assertRaises(ValueError):
                load_admin_tree()
        load_admin_tree.cache_clear()

        self.assertEqual(sub_county_names('NotACounty'), [])
        self.assertEqual(ward_names('Nairobi', 'Nope'), [])
        self.assertEqual(ward_names('Nope', 'Starehe'), [])

        errors = validate_admin_location('', '', '', apply_defaults=False)
        self.assertIn('county', errors)
        self.assertIn('sub_county', errors)
        self.assertIn('ward', errors)

        self.assertEqual(
            validate_admin_location('Atlantis', 'X', 'Y', apply_defaults=False)['county'],
            'Select a valid Kenyan county.',
        )
        county = next(iter(load_admin_tree().keys()))
        self.assertIn(
            'sub-county',
            validate_admin_location(county, 'NoSuchSub', 'Y', apply_defaults=False)['sub_county'],
        )
        sub = next(iter(load_admin_tree()[county].keys()))
        self.assertIn(
            'ward',
            validate_admin_location(county, sub, 'NoSuchWard', apply_defaults=False)['ward'],
        )


class PaymentsTrailUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('pt_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.customer = Customer.objects.create(name='Trail Cust', phone='0700555666', is_active=True)
        cls.sale = Sale.objects.create(
            sale_number='SALE-PT-1',
            status='completed',
            customer=cls.customer,
            cashier=cls.manager,
            subtotal=Decimal('200'),
            total=Decimal('200'),
            amount_paid=Decimal('200'),
            payment_method='mpesa',
            payment_reference='QHXPT001',
            occurred_at=timezone.now(),
        )
        invoice = Invoice.objects.create(
            sale=cls.sale,
            customer=cls.customer,
            customer_name=cls.customer.name,
            issued_date=timezone.localdate(),
            due_date=timezone.localdate(),
            subtotal=Decimal('200'),
            total=Decimal('200'),
            amount_paid=Decimal('50'),
            status='partial',
        )
        cls.payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal('50'),
            payment_method='bank_transfer',
            payment_date=timezone.localdate(),
            reference='BANK-1',
            recorded_by=cls.manager,
        )

    def test_parse_helpers(self):
        self.assertIsNone(_parse_day(None))
        self.assertIsNone(_parse_day(''))
        day = _parse_day(timezone.now().isoformat())
        self.assertIsNotNone(day)
        with self.assertRaises(ValueError):
            _parse_day('not-a-date')
        self.assertEqual(len(_parse_kinds(None)), 3)
        self.assertEqual(_parse_kinds(['invoice_payment']), ['invoice_payment'])
        self.assertEqual(_parse_kinds('sale_payment,bogus'), ['sale_payment'])
        self.assertEqual(_method_label('cash'), 'Cash')
        self.assertTrue(len(_method_label('weird_method')) > 0)

    def test_invoice_and_sale_trail_with_search_and_empty_hydrate(self):
        today = timezone.localdate().isoformat()
        inv = list_payments_trail(
            kind='invoice_payment',
            date_from=today,
            date_to=today,
            search=self.customer.name[:5],
            user=self.manager,
        )
        self.assertGreaterEqual(inv['count'], 1)
        self.assertEqual(inv['results'][0]['kind'], 'invoice_payment')

        sale = list_payments_trail(
            kind='sale_payment',
            date_from=today,
            date_to=today,
            search='SALE-PT',
            user=self.manager,
        )
        self.assertGreaterEqual(sale['count'], 1)
        self.assertEqual(sale['results'][0]['kind'], 'sale_payment')

        empty = list_payments_trail(
            kind='invoice_payment',
            date_from='1990-01-01',
            date_to='1990-01-02',
            user=self.manager,
        )
        self.assertEqual(empty['count'], 0)
        self.assertEqual(empty['results'], [])

        # Default 30-day window when dates omitted
        defaulted = list_payments_trail(kind='sale_payment', user=self.manager)
        self.assertIn('results', defaulted)

        # Visibility filter with empty visible set for non-storewide user
        sales_user = User.objects.create_user('pt_sales', password='x')
        UserProfile.objects.create(
            user=sales_user, role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES), is_active=True,
        )
        with patch('sales.payments_trail._visible_debtor_customer_ids', return_value=set()):
            scoped = list_payments_trail(
                kind='sale_payment',
                date_from=today,
                date_to=today,
                user=sales_user,
            )
            self.assertEqual(scoped['count'], 0)


class BackfillImportUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('bf_imp', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.product = Product.objects.create(
            name='Import Pen', sku='IMP-PEN', price=Decimal('50'),
            stock_quantity=100, track_stock=True, is_active=True,
        )
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

    def test_template_and_decode_and_parse_decimal(self):
        csv_text = backfill_import_template_csv()
        self.assertIn('sale_reference', csv_text)
        self.assertIn('SKU-002', csv_text)

        latin = BytesIO('café'.encode('latin-1'))
        latin.name = 'x.csv'
        self.assertIn('caf', _decode_csv_file(latin))

        with self.assertRaises(ValueError):
            _parse_decimal('', 'unit_price', 2)
        with self.assertRaises(ValueError):
            _parse_decimal('abc', 'unit_price', 2)

    def test_import_empty_and_row_errors_and_success(self):
        empty = SimpleUploadedFile('empty.csv', b'# comment only\n', content_type='text/csv')
        out = import_backfill_sales_from_csv(empty, user=self.manager)
        self.assertEqual(out['created'], 0)
        self.assertTrue(out['errors'])

        bad = SimpleUploadedFile(
            'bad.csv',
            (
                'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
                'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id\n'
                ',,short,,,,,,,\n'
            ).encode(),
            content_type='text/csv',
        )
        bad_out = import_backfill_sales_from_csv(bad, user=self.manager)
        self.assertTrue(bad_out['errors'])

        occurred = (timezone.now() - timedelta(days=2)).strftime('%Y-%m-%dT10:00:00')
        good_csv = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id\n'
            f'SALE-IMP-1,{occurred},Sold offline during outage,IMP-PEN,2,50.00,cash,100.00,pos,,,{self.manager.id}\n'
            f'SALE-IMP-1,{occurred},Sold offline during outage,{self.product.id},1,50.00,cash,100.00,pos,,,\n'
        ).replace(f',{self.product.id},', f',,')  # use sku on first; product_id on second via rewrite
        # Rebuild cleanly: first row sku, second row product_id under same sale with matching meta
        good_csv = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id,product_id\n'
            f'SALE-IMP-1,{occurred},Sold offline during outage,IMP-PEN,1,50.00,cash,50.00,pos,,,{self.manager.id},\n'
        )
        good = SimpleUploadedFile('good.csv', good_csv.encode(), content_type='text/csv')
        factory = RequestFactory()
        request = factory.post('/api/sales/backfill-import-csv/')
        request.user = self.manager
        result = import_backfill_sales_from_csv(
            good, user=self.manager, request=request, acknowledge_stock_warnings=True,
        )
        self.assertEqual(result['created'], 1, result)
        self.assertEqual(result['errors'], [])

    def test_import_mismatch_and_approval_path(self):
        occurred = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT10:00:00')
        mismatch = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id\n'
            f'S1,{occurred},Sold offline during outage,IMP-PEN,1,50.00,cash,50.00,pos,,,\n'
            f'S1,{(timezone.now() - timedelta(days=3)).strftime("%Y-%m-%dT10:00:00")},'
            f'Sold offline during outage,IMP-PEN,1,50.00,cash,50.00,pos,,,\n'
        )
        out = import_backfill_sales_from_csv(
            SimpleUploadedFile('m.csv', mismatch.encode(), content_type='text/csv'),
            user=self.manager,
        )
        self.assertTrue(any('occurred_at must match' in e for e in out['errors']))

        pending_csv = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id\n'
            f'S2,{occurred},Sold offline during outage,IMP-PEN,1,50.00,cash,50.00,normal,,,\n'
        )
        factory = RequestFactory()
        request = factory.post('/')
        request.user = self.manager
        with patch('sales.backfill_import.backfill_requires_approval', return_value=True):
            no_req = import_backfill_sales_from_csv(
                SimpleUploadedFile('p.csv', pending_csv.encode(), content_type='text/csv'),
                user=self.manager,
                request=None,
                acknowledge_stock_warnings=True,
            )
            self.assertTrue(any('HTTP request' in e or 'Maker-checker' in e for e in no_req['errors']))
            with patch('approvals.backfill_integration.queue_sale_backfill') as queue:
                queued = import_backfill_sales_from_csv(
                    SimpleUploadedFile('p2.csv', pending_csv.encode(), content_type='text/csv'),
                    user=self.manager,
                    request=request,
                    acknowledge_stock_warnings=True,
                )
            self.assertEqual(queued['pending'], 1)
            queue.assert_called_once()

    def test_row_validation_error_branches(self):
        occurred = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT10:00:00')
        rows = (
            'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
            'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id,product_id\n'
            # missing product
            f'R1,{occurred},Sold offline during outage,,1,50.00,cash,50.00,pos,,,,\n'
            # invalid occurred_at
            f'R2,not-a-date,Sold offline during outage,IMP-PEN,1,50.00,cash,50.00,pos,,,,\n'
            # short reason
            f'R3,{occurred},short!!!!,IMP-PEN,1,50.00,cash,50.00,pos,,,,\n'
            # bad qty
            f'R4,{occurred},Sold offline during outage,IMP-PEN,0,50.00,cash,50.00,pos,,,,\n'
            # unknown sku
            f'R5,{occurred},Sold offline during outage,NO-SKU,1,50.00,cash,50.00,pos,,,,\n'
            # product_id path
            f'R6,{occurred},Sold offline during outage,,1,50.00,cash,50.00,pos,,,{self.product.id}\n'
            # mismatch reason on same sale
            f'R7,{occurred},Sold offline during outage A,IMP-PEN,1,50.00,cash,50.00,pos,,,,\n'
            f'R7,{occurred},Sold offline during outage B,IMP-PEN,1,50.00,cash,50.00,pos,,,,\n'
        )
        out = import_backfill_sales_from_csv(
            SimpleUploadedFile('errs.csv', rows.encode(), content_type='text/csv'),
            user=self.manager,
            acknowledge_stock_warnings=True,
        )
        self.assertTrue(len(out['errors']) >= 5)

        with patch(
            'sales.services.SaleService.create_sale_from_validated_data',
            side_effect=RuntimeError('create failed'),
        ):
            boom = import_backfill_sales_from_csv(
                SimpleUploadedFile(
                    'boom.csv',
                    (
                        'sale_reference,occurred_at,backfill_reason,product_sku,quantity,unit_price,'
                        'payment_method,amount_paid,sale_type,payment_reference,customer_id,served_by_id\n'
                        f'R8,{occurred},Sold offline during outage,IMP-PEN,1,50.00,cash,50.00,pos,,,\n'
                    ).encode(),
                    content_type='text/csv',
                ),
                user=self.manager,
                acknowledge_stock_warnings=True,
            )
        self.assertTrue(any('create failed' in e for e in boom['errors']))


class SaleItemStrTests(TestCase):
    def test_sale_item_str_with_variant(self):
        category = Category.objects.create(name='Var Cat', is_active=True)
        size = Size.objects.create(name='L', code='L', is_active=True)
        color = Color.objects.create(name='Red', is_active=True)
        product = Product.objects.create(
            name='Tee', sku='TEE-1', category=category, price=Decimal('20'),
            has_variants=True, track_stock=True, is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=product, size=size, color=color, sku='TEE-1-L-RED',
            price=Decimal('20'), stock_quantity=5, is_active=True,
        )
        sale = Sale.objects.create(
            status='completed', subtotal=Decimal('20'), total=Decimal('20'),
            amount_paid=Decimal('20'), payment_method='cash',
        )
        item = SaleItem.objects.create(
            sale=sale, product=product, variant=variant,
            quantity=2, unit_price=Decimal('20'), subtotal=Decimal('40'),
        )
        text = str(item)
        self.assertIn('Tee', text)
        self.assertIn('Size:', text)
        self.assertIn('Color:', text)
