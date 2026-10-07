"""Mobile Sasa provider + customer sale/debt SMS."""

from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from messaging.customer_notify import (
    notify_customer_debt_settlement,
    notify_customer_sale_completed,
)
from messaging.models import MessageOutbox
from messaging.providers import (
    FakeSmsProvider,
    MobileSasaSmsProvider,
    build_sms_provider_from_settings,
    set_sms_provider,
)
from messaging.templates_sms import (
    customer_first_name,
    format_balance_note,
    format_payment_ref_note,
    format_sale_items_summary,
    format_sale_number_for_sms,
    render_debt_settlement_sms,
    render_sale_completed_sms,
    sale_number_token,
)
from products.models import Category, Product
from sales.models import Customer, Sale, SaleItem
from sales.services import CustomerService


class SaleNumberFormatUnitTests(SimpleTestCase):
    def test_sale_number_token_and_short_format(self):
        self.assertEqual(sale_number_token('SALE-0001'), '0001')
        self.assertEqual(sale_number_token('HOLD-042'), '042')
        self.assertEqual(
            format_sale_number_for_sms('SALE-ABC12', short=True, prefix='S-'),
            'S-ABC12',
        )
        self.assertEqual(
            format_sale_number_for_sms('SALE-ABC12', short=False, prefix='S-'),
            'SALE-ABC12',
        )
        self.assertEqual(
            format_sale_number_for_sms('SALE-9', short=True, prefix='REF-'),
            'REF-9',
        )

    def test_items_summary_is_minified_receipt(self):
        class _P:
            name = 'Bar soap deluxe long name'

        class _I:
            product = _P()
            quantity = 2
            unit_price = Decimal('200')
            subtotal = Decimal('400')
            size = None
            color = None
            variant = None

        class _I2:
            product = type('P', (), {'name': 'Oil'})()
            quantity = 1
            unit_price = Decimal('1100')
            subtotal = Decimal('1100')
            size = None
            color = None
            variant = None

        summary = format_sale_items_summary([_I(), _I2()])
        self.assertIn('2 @ 200', summary)
        self.assertIn('Oil 1 @ 1100', summary)
        self.assertIn('…', summary)  # long name truncated
        self.assertIn(', ', summary)


class TemplateSmsTests(TestCase):
    def test_first_name_prefers_owner(self):
        c = Customer(
            name='Sunrise Duka',
            owner_name='Jane Wambui',
            contact_person='Clerk',
        )
        self.assertEqual(customer_first_name(c), 'Jane')

    def test_sale_and_settlement_templates(self):
        paid = render_sale_completed_sms(
            first_name='Jane',
            sale_number='SALE-1',
            total='1000',
            paid='1000',
            balance_owed=None,
            items_summary='Soap 2 @ 500',
        )
        self.assertIn('Hi Jane, your order S-1.', paid)
        self.assertIn('Soap 2 @ 500', paid)
        self.assertIn('Total KES 1000', paid)
        self.assertNotIn('SALE-1', paid)
        self.assertNotIn('Balance now', paid)
        self.assertNotIn(' Ref ', paid)

        debt = render_sale_completed_sms(
            first_name='Jane',
            sale_number='SALE-2',
            total='1000',
            paid='400',
            balance_owed='600',
            items_summary='Oil 1 @ 1000',
            payment_reference='QHX1ABC2DE',
        )
        self.assertIn('your order S-2.', debt)
        self.assertIn('Balance now KES 600', debt)
        self.assertIn('Oil 1 @ 1000', debt)
        self.assertIn('Ref QHX1ABC2DE', debt)

        settled = render_debt_settlement_sms(
            first_name='Jane',
            amount='200',
            balance_owed='400',
            payment_reference='QHX99',
        )
        self.assertIn('received KES 200', settled)
        self.assertIn('Balance now KES 400', settled)
        self.assertIn('Ref QHX99', settled)

        cleared = render_debt_settlement_sms(
            first_name='Jane',
            amount='400',
            balance_owed='0',
            payment_reference='QHX00',
        )
        self.assertIn('Ref QHX00', cleared)
        self.assertNotIn('Balance now', cleared)

    def test_balance_and_payment_ref_helpers_respect_flags(self):
        self.assertEqual(format_balance_note(0, show_when_zero=False), '')
        self.assertEqual(
            format_balance_note(0, show_when_zero=True),
            ' Balance now KES 0.',
        )
        self.assertEqual(
            format_balance_note(50, show_when_zero=False),
            ' Balance now KES 50.',
        )
        self.assertEqual(
            format_payment_ref_note('QHX1', include=True),
            ' Ref QHX1.',
        )
        self.assertEqual(format_payment_ref_note('QHX1', include=False), '')
        self.assertEqual(format_payment_ref_note('', include=True), '')


class MobileSasaProviderTests(SimpleTestCase):
    def test_missing_config(self):
        p = MobileSasaSmsProvider(api_token='', sender_id='X')
        self.assertFalse(p.send(to='0712345678', body='hi').ok)

    @patch('messaging.providers.urllib.request.urlopen')
    def test_success_parses_message_id(self, mock_urlopen):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return (
                    b'{"status":true,"responseCode":"0200","message":"Accepted",'
                    b'"messageId":"abc-123"}'
                )

        mock_urlopen.return_value = _Resp()
        p = MobileSasaSmsProvider(api_token='mbs_x', sender_id='SHOP')
        result = p.send(to='0712345678', body='Hi Jane')
        self.assertTrue(result.ok)
        self.assertEqual(result.provider_ref, 'abc-123')

    @override_settings(
        SMS_PROVIDER='mobilesasa',
        MOBILESASA_API_TOKEN='mbs_t',
        MOBILESASA_SENDER_ID='SHOP',
    )
    def test_settings_pick_mobilesasa(self):
        set_sms_provider(None)
        provider = build_sms_provider_from_settings()
        self.assertIsInstance(provider, MobileSasaSmsProvider)
        self.assertEqual(provider.name, 'mobilesasa')


class CustomerNotifyTests(TestCase):
    def setUp(self):
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        self.customer = Customer.objects.create(
            name='Sunrise Duka',
            owner_name='Jane Wambui',
            phone='0712345678',
            wallet_balance=Decimal('0'),
        )

    def tearDown(self):
        set_sms_provider(None)

    def test_sale_completed_queues_and_sends(self):
        sale = Sale.objects.create(
            customer=self.customer,
            sale_number='SALE-SMS-1',
            status='completed',
            sale_type='pos',
            subtotal=Decimal('500.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('500.00'),
            amount_paid=Decimal('500.00'),
            change=Decimal('0'),
            payment_method='mpesa',
            payment_reference='QHX1ABC2DE',
        )
        cat = Category.objects.create(name='SMS Cat', is_active=True)
        product = Product.objects.create(
            name='Soap',
            sku='SMS-SOAP-1',
            category=cat,
            price=Decimal('250'),
            cost=Decimal('100'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=2,
            unit_price=Decimal('250'),
            subtotal=Decimal('500'),
        )
        with self.captureOnCommitCallbacks(execute=True):
            msg = notify_customer_sale_completed(sale)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.template_key, MessageOutbox.TEMPLATE_SALE_COMPLETED)
        self.assertEqual(len(self.sms.sent), 1)
        body = self.sms.sent[0]['body']
        self.assertIn('Hi Jane', body)
        self.assertIn('S-1', body)
        self.assertNotIn('SALE-SMS-1', body)
        self.assertIn('your order S-1.', body)
        self.assertIn('Soap 2 @ 250', body)
        self.assertIn('Total KES 500', body)
        self.assertIn('Ref QHX1ABC2DE', body)
        self.assertNotIn('Balance now', body)

    def test_backfill_skipped(self):
        sale = Sale.objects.create(
            customer=self.customer,
            sale_number='SALE-BF-1',
            status='completed',
            sale_type='pos',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            change=Decimal('0'),
            payment_method='cash',
            entry_source='backfill',
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(notify_customer_sale_completed(sale))
        self.assertEqual(len(self.sms.sent), 0)

    def test_debt_settlement_sms(self):
        self.customer.wallet_balance = Decimal('-300.00')
        self.customer.save(update_fields=['wallet_balance'])
        with self.captureOnCommitCallbacks(execute=True):
            CustomerService().record_wallet_payment(
                customer=self.customer,
                amount=Decimal('100.00'),
                payment_method='mpesa',
                reference='QHXDEB01',
            )
        self.assertEqual(len(self.sms.sent), 1)
        body = self.sms.sent[0]['body']
        self.assertIn('Hi Jane', body)
        self.assertIn('100', body)
        self.assertIn('Ref QHXDEB01', body)
        self.assertIn('Balance now KES 200', body)
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=MessageOutbox.TEMPLATE_DEBT_SETTLEMENT,
                status=MessageOutbox.STATUS_SENT,
            ).count(),
            1,
        )

    def test_debt_settlement_omits_zero_balance(self):
        self.customer.wallet_balance = Decimal('-100.00')
        self.customer.save(update_fields=['wallet_balance'])
        with self.captureOnCommitCallbacks(execute=True):
            CustomerService().record_wallet_payment(
                customer=self.customer,
                amount=Decimal('100.00'),
                payment_method='cash',
                reference='CASH-1',
            )
        self.assertEqual(len(self.sms.sent), 1)
        body = self.sms.sent[0]['body']
        self.assertIn('Ref CASH-1', body)
        self.assertNotIn('Balance now', body)

    def test_no_phone_skips(self):
        self.customer.phone = ''
        self.customer.save(update_fields=['phone'])
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(
                notify_customer_debt_settlement(
                    self.customer, amount=Decimal('50'),
                )
            )
        self.assertEqual(len(self.sms.sent), 0)
