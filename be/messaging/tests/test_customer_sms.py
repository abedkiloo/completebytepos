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
    render_debt_settlement_sms,
    render_sale_completed_sms,
)
from sales.models import Customer, Sale
from sales.services import CustomerService


class TemplateSmsTests(SimpleTestCase):
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
        )
        self.assertIn('Hi Jane', paid)
        self.assertIn('SALE-1', paid)
        self.assertNotIn('Balance now', paid)

        debt = render_sale_completed_sms(
            first_name='Jane',
            sale_number='SALE-2',
            total='1000',
            paid='400',
            balance_owed='600',
        )
        self.assertIn('Balance now KES 600', debt)

        settled = render_debt_settlement_sms(
            first_name='Jane', amount='200', balance_owed='400',
        )
        self.assertIn('received KES 200', settled)
        self.assertIn('Balance now KES 400', settled)


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
            payment_method='cash',
        )
        with self.captureOnCommitCallbacks(execute=True):
            msg = notify_customer_sale_completed(sale)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.template_key, MessageOutbox.TEMPLATE_SALE_COMPLETED)
        self.assertEqual(len(self.sms.sent), 1)
        self.assertIn('Hi Jane', self.sms.sent[0]['body'])
        self.assertIn('SALE-SMS-1', self.sms.sent[0]['body'])

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
                payment_method='cash',
            )
        self.assertEqual(len(self.sms.sent), 1)
        body = self.sms.sent[0]['body']
        self.assertIn('Hi Jane', body)
        self.assertIn('100', body)
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=MessageOutbox.TEMPLATE_DEBT_SETTLEMENT,
                status=MessageOutbox.STATUS_SENT,
            ).count(),
            1,
        )

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
