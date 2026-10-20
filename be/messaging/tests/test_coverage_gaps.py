"""Focused coverage for messaging views, providers, notify, and templates."""

from __future__ import annotations

import json
import urllib.error
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from messaging import providers as providers_mod
from messaging.customer_notify import (
    dispatch_outbox,
    notify_customer_debt_increase,
    notify_customer_debt_settlement,
    notify_customer_sale_completed,
    notify_customer_welcome,
)
from messaging.models import MessageOutbox, SmsTemplate
from messaging.providers import (
    AfricasTalkingSmsProvider,
    FakeSmsProvider,
    MobileSasaSmsProvider,
    build_sms_provider_from_settings,
    get_sms_provider,
    set_sms_provider,
)
from messaging.services import (
    MessagingError,
    reset_sms_template,
    save_sms_template,
    send_debt_reminders,
    serialize_template,
)
from messaging.templates_sms import (
    customer_first_name,
    customer_greeting_name,
    format_balance_note,
    format_payment_ref_note,
    format_sale_items_summary,
    format_sale_number_for_sms,
    sale_number_token,
    sms_cap_name,
)
from sales.models import Customer


class MessagingPermissionDeniedTests(APITestCase):
    """Hit 403 / validation branches that sales-role tests skip."""

    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('msg_noperm', password='x')
        # Profile without messaging / customers / debt_management create/view.
        UserProfile.objects.create(
            user=cls.user,
            role='cashier',
            custom_role=None,
            is_active=True,
        )
        cls.debtor = Customer.objects.create(
            name='Owes', phone='0700111222', wallet_balance=Decimal('-100.00'),
        )

    def setUp(self):
        set_sms_provider(FakeSmsProvider())
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def tearDown(self):
        set_sms_provider(None)

    def test_templates_and_debt_denied(self):
        self.assertEqual(self.client.get('/api/messaging/templates/').status_code, 403)
        self.assertEqual(
            self.client.get('/api/messaging/templates/debt_reminder/').status_code, 403,
        )
        self.assertEqual(self.client.post('/api/messaging/reminders/debt/').status_code, 403)
        self.assertEqual(
            self.client.get('/api/messaging/reminders/debt/template/').status_code, 403,
        )
        self.assertEqual(
            self.client.get('/api/messaging/reminders/debt/preview/').status_code, 403,
        )
        self.assertEqual(
            self.client.post('/api/messaging/reminders/debt/send/').status_code, 403,
        )

    def test_blast_and_week_denied(self):
        self.assertEqual(
            self.client.get('/api/messaging/blast/preview/?template_key=promo_customer_week').status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                '/api/messaging/blast/send/',
                {'template_key': 'promo_customer_week'},
                format='json',
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get('/api/messaging/promos/customer-week/preview/').status_code, 403,
        )
        self.assertEqual(
            self.client.post('/api/messaging/promos/customer-week/send/', {}, format='json').status_code,
            403,
        )


class MessagingTemplateEditTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('msg_tpl_edit', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def setUp(self):
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_template_detail_get_unknown_and_reset(self):
        missing = self.client.get('/api/messaging/templates/not_a_real_key/')
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

        save_sms_template('debt_reminder', 'Hi {name} owe {amount}', user=self.user)
        reset = self.client.delete('/api/messaging/templates/debt_reminder/')
        self.assertEqual(reset.status_code, status.HTTP_200_OK, reset.data)
        self.assertFalse(reset.data.get('is_customized'))

    def test_template_put_requires_body(self):
        res = self.client.put(
            '/api/messaging/templates/debt_reminder/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_debt_template_put_and_preview_bad_ids(self):
        get_ok = self.client.get('/api/messaging/reminders/debt/template/')
        self.assertEqual(get_ok.status_code, status.HTTP_200_OK)

        no_body = self.client.put(
            '/api/messaging/reminders/debt/template/',
            {},
            format='json',
        )
        self.assertEqual(no_body.status_code, status.HTTP_400_BAD_REQUEST)

        bad = self.client.post(
            '/api/messaging/reminders/debt/preview/',
            {'customer_ids': ['x']},
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        empty_send = self.client.post(
            '/api/messaging/reminders/debt/send/',
            {'customer_ids': []},
            format='json',
        )
        self.assertEqual(empty_send.status_code, status.HTTP_400_BAD_REQUEST)

        bad_send = self.client.post(
            '/api/messaging/reminders/debt/send/',
            {'customer_ids': ['nope']},
            format='json',
        )
        self.assertEqual(bad_send.status_code, status.HTTP_400_BAD_REQUEST)


class MessagingBlastValidationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('msg_blast_val', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Aisha', phone='0700999888', is_active=True,
        )

    def setUp(self):
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def tearDown(self):
        set_sms_provider(None)

    def test_blast_preview_validation(self):
        missing_key = self.client.get('/api/messaging/blast/preview/')
        self.assertEqual(missing_key.status_code, status.HTTP_400_BAD_REQUEST)

        unknown = self.client.post(
            '/api/messaging/blast/preview/',
            {'template_key': 'nope'},
            format='json',
        )
        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)

        bad_scope = self.client.post(
            '/api/messaging/blast/preview/',
            {'template_key': SmsTemplate.KEY_CUSTOMER_WEEK, 'scope': 'team'},
            format='json',
        )
        self.assertEqual(bad_scope.status_code, status.HTTP_400_BAD_REQUEST)

        bad_one = self.client.post(
            '/api/messaging/blast/preview/',
            {
                'template_key': SmsTemplate.KEY_CUSTOMER_WEEK,
                'scope': 'one',
                'customer_id': 'abc',
            },
            format='json',
        )
        self.assertEqual(bad_one.status_code, status.HTTP_400_BAD_REQUEST)

        bad_ids = self.client.post(
            '/api/messaging/blast/preview/',
            {
                'template_key': SmsTemplate.KEY_CUSTOMER_WEEK,
                'customer_ids': ['x'],
            },
            format='json',
        )
        self.assertEqual(bad_ids.status_code, status.HTTP_400_BAD_REQUEST)

        empty_ids = self.client.post(
            '/api/messaging/blast/send/',
            {
                'template_key': SmsTemplate.KEY_CUSTOMER_WEEK,
                'customer_ids': [],
            },
            format='json',
        )
        self.assertEqual(empty_ids.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_week_validation_and_send(self):
        bad_id = self.client.post(
            '/api/messaging/promos/customer-week/preview/',
            {'customer_id': 'zz'},
            format='json',
        )
        self.assertEqual(bad_id.status_code, status.HTTP_400_BAD_REQUEST)

        bad_ids = self.client.post(
            '/api/messaging/promos/customer-week/preview/',
            {'customer_ids': ['zz']},
            format='json',
        )
        self.assertEqual(bad_ids.status_code, status.HTTP_400_BAD_REQUEST)

        empty_send = self.client.post(
            '/api/messaging/promos/customer-week/send/',
            {'customer_ids': []},
            format='json',
        )
        self.assertEqual(empty_send.status_code, status.HTTP_400_BAD_REQUEST)

        bad_send_id = self.client.post(
            '/api/messaging/promos/customer-week/send/',
            {'customer_id': 'nope'},
            format='json',
        )
        self.assertEqual(bad_send_id.status_code, status.HTTP_400_BAD_REQUEST)

        ok = self.client.post(
            '/api/messaging/promos/customer-week/send/',
            {'scope': 'one', 'customer_id': self.customer.id},
            format='json',
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED, ok.data)


class MobileSasaProviderTests(SimpleTestCase):
    def test_send_validation_and_success(self):
        p = MobileSasaSmsProvider(api_token='', sender_id='OMUWENGA')
        self.assertFalse(p.send(to='2547', body='hi').ok)

        p = MobileSasaSmsProvider(api_token='tok', sender_id='')
        self.assertFalse(p.send(to='2547', body='hi').ok)

        p = MobileSasaSmsProvider(api_token='tok', sender_id='OMUWENGA')
        self.assertFalse(p.send(to='', body='hi').ok)

        with patch('messaging.providers._mobilesasa_post', return_value=(None, 'HTTP 500')):
            self.assertFalse(p.send(to='254700', body='hi').ok)

        with patch(
            'messaging.providers._mobilesasa_post',
            return_value=({'status': True, 'messageId': 'm1'}, ''),
        ):
            ok = p.send(to='254700', body='hi')
            self.assertTrue(ok.ok)
            self.assertEqual(ok.provider_ref, 'm1')

        with patch(
            'messaging.providers._mobilesasa_post',
            return_value=({'status': False, 'responseCode': '0400', 'message': 'bad'}, ''),
        ):
            self.assertFalse(p.send(to='254700', body='hi').ok)

    def test_bulk_and_personalized(self):
        p = MobileSasaSmsProvider(api_token='tok', sender_id='OMUWENGA')
        self.assertFalse(p.send_bulk(phones=[], body='x').ok)
        self.assertFalse(p.send_bulk(phones=['2547'], body='  ').ok)
        self.assertFalse(
            MobileSasaSmsProvider(api_token='', sender_id='X').send_bulk(
                phones=['2547'], body='hi',
            ).ok
        )
        self.assertFalse(
            MobileSasaSmsProvider(api_token='t', sender_id='').send_bulk(
                phones=['2547'], body='hi',
            ).ok
        )

        with patch(
            'messaging.providers._mobilesasa_post',
            return_value=({'status': True, 'bulkId': 'b1'}, ''),
        ):
            ok = p.send_bulk(phones=['254700111', '254700222'], body='promo')
            self.assertTrue(ok.ok)
            self.assertEqual(ok.accepted_count, 2)

        with patch('messaging.providers._mobilesasa_post', return_value=(None, 'down')):
            self.assertFalse(p.send_bulk(phones=['2547'], body='hi').ok)

        with patch(
            'messaging.providers._mobilesasa_post',
            return_value=({'status': False, 'message': 'no'}, ''),
        ):
            self.assertFalse(p.send_bulk(phones=['2547'], body='hi').ok)

        self.assertFalse(p.send_bulk_personalized(messages=[]).ok)
        self.assertFalse(
            MobileSasaSmsProvider(api_token='', sender_id='X').send_bulk_personalized(
                messages=[{'phone': '2547', 'message': 'hi'}],
            ).ok
        )
        self.assertFalse(
            MobileSasaSmsProvider(api_token='t', sender_id='').send_bulk_personalized(
                messages=[{'phone': '2547', 'message': 'hi'}],
            ).ok
        )

        with patch(
            'messaging.providers._mobilesasa_post',
            return_value=({'responseCode': '0200', 'bulkId': 'bp'}, ''),
        ):
            ok = p.send_bulk_personalized(
                messages=[{'phone': '2547', 'message': 'hi'}, {'phone': '', 'message': 'x'}],
            )
            self.assertTrue(ok.ok)

        with patch('messaging.providers._mobilesasa_post', return_value=(None, 'err')):
            self.assertFalse(
                p.send_bulk_personalized(
                    messages=[{'phone': '2547', 'message': 'hi'}],
                ).ok
            )
        with patch(
            'messaging.providers._mobilesasa_post',
            return_value=({'status': False, 'error': 'reject'}, ''),
        ):
            self.assertFalse(
                p.send_bulk_personalized(
                    messages=[{'phone': '2547', 'message': 'hi'}],
                ).ok
            )

    def test_mobilesasa_post_http_and_generic_errors(self):
        class FakeHTTPError(urllib.error.HTTPError):
            def __init__(self):
                super().__init__('http://x', 502, 'Bad Gateway', hdrs=None, fp=None)

            def read(self):
                return b'{"error":"gateway"}'

        with patch('messaging.providers.urllib.request.urlopen', side_effect=FakeHTTPError()):
            data, err = providers_mod._mobilesasa_post(
                'http://x', 'tok', {'a': 1}, 1.0,
            )
            self.assertIsNone(data)
            self.assertIn('HTTP 502', err)

        with patch(
            'messaging.providers.urllib.request.urlopen',
            side_effect=RuntimeError('timeout'),
        ):
            data, err = providers_mod._mobilesasa_post(
                'http://x', 'tok', {'a': 1}, 1.0,
            )
            self.assertIsNone(data)
            self.assertIn('timeout', err)

        class OkResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({'status': True}).encode()

        with patch('messaging.providers.urllib.request.urlopen', return_value=OkResp()):
            data, err = providers_mod._mobilesasa_post(
                'http://x', 'tok', {'a': 1}, 1.0,
            )
            self.assertEqual(err, '')
            self.assertTrue(data.get('status'))

    def test_fake_bulk_fail_and_at_bulk(self):
        fake = FakeSmsProvider(fail_bulk_next=True)
        self.assertFalse(fake.send_bulk_personalized(messages=[{'phone': '1', 'message': 'x'}]).ok)
        at = AfricasTalkingSmsProvider(api_key='k', username='u')
        self.assertFalse(at.send_bulk_personalized(messages=[]).ok)

    @override_settings(SMS_LIVE_DISABLED=True)
    def test_build_provider_from_settings(self):
        set_sms_provider(None)
        providers_mod._provider = None
        self.assertIsInstance(build_sms_provider_from_settings(), FakeSmsProvider)

    @override_settings(
        SMS_LIVE_DISABLED=False,
        SMS_PROVIDER='mobilesasa',
        MOBILESASA_API_TOKEN='tok',
        MOBILESASA_SENDER_ID='OMU',
    )
    def test_build_mobilesasa(self):
        p = build_sms_provider_from_settings()
        self.assertIsInstance(p, MobileSasaSmsProvider)

    @override_settings(
        SMS_LIVE_DISABLED=False,
        SMS_PROVIDER='africastalking',
        AFRICASTALKING_API_KEY='k',
        AFRICASTALKING_USERNAME='u',
    )
    def test_build_at(self):
        p = build_sms_provider_from_settings()
        self.assertIsInstance(p, AfricasTalkingSmsProvider)

    @override_settings(SMS_LIVE_DISABLED=False, SMS_PROVIDER='fake')
    def test_build_fake_choice(self):
        self.assertIsInstance(build_sms_provider_from_settings(), FakeSmsProvider)


class CustomerNotifyTests(TestCase):
    def setUp(self):
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        self.customer = Customer.objects.create(
            name='Duka West',
            owner_name='Grace Achieng',
            phone='0700111222',
            wallet_balance=Decimal('-200.00'),
        )

    def tearDown(self):
        set_sms_provider(None)

    def test_dispatch_failure_and_notify_paths(self):
        msg = MessageOutbox.objects.create(
            to_phone='0700111222',
            body='hi',
            template_key=MessageOutbox.TEMPLATE_CUSTOMER_WELCOME,
            customer=self.customer,
        )
        self.sms.fail_next = True
        failed = dispatch_outbox(msg)
        self.assertEqual(failed.status, MessageOutbox.STATUS_FAILED)

        self.assertIsNone(notify_customer_sale_completed(SimpleNamespace(customer=None)))
        sale = SimpleNamespace(
            customer=self.customer,
            entry_source='backfill',
            pk=1,
        )
        self.assertIsNone(notify_customer_sale_completed(sale))

        sale = SimpleNamespace(
            customer=self.customer,
            entry_source='pos',
            pk=9,
            sale_number='SALE-9',
            amount_paid=Decimal('50'),
            total=Decimal('100'),
            payment_reference='MPESA1',
            items=SimpleNamespace(select_related=lambda *a: SimpleNamespace(all=lambda: [])),
        )
        with self.captureOnCommitCallbacks(execute=True):
            queued = notify_customer_sale_completed(sale)
        self.assertIsNotNone(queued)

        self.assertIsNone(notify_customer_debt_increase(None, amount=10))
        self.assertIsNone(notify_customer_debt_increase(self.customer, amount=0))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNotNone(notify_customer_debt_increase(self.customer, amount=25))

        self.assertIsNone(notify_customer_debt_settlement(None, amount=10))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNotNone(
                notify_customer_debt_settlement(
                    self.customer, amount=10, payment_reference='R1',
                )
            )

        self.assertIsNone(notify_customer_welcome(None))
        no_phone = Customer.objects.create(name='Silent', phone='')
        self.assertIsNone(notify_customer_welcome(no_phone))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNotNone(notify_customer_welcome(self.customer))

        with patch(
            'messaging.customer_notify.render_sale_completed_sms',
            side_effect=RuntimeError('boom'),
        ):
            self.assertIsNone(notify_customer_sale_completed(sale))


class TemplatesSmsUnitTests(SimpleTestCase):
    def test_helpers(self):
        self.assertEqual(sms_cap_name('', fallback='X'), 'X')
        self.assertEqual(sms_cap_name('[west]', fallback='X'), 'X')
        self.assertEqual(sms_cap_name('mama mboga [west]', first_word_only=True), 'Mama')
        self.assertEqual(sale_number_token(''), '')
        self.assertEqual(sale_number_token('SALE-0001'), '0001')
        self.assertEqual(sale_number_token('HOLD_042'), '042')
        self.assertEqual(sale_number_token('ABC99'), '99')
        self.assertEqual(sale_number_token('PLAIN'), 'PLAIN')
        self.assertEqual(
            format_sale_number_for_sms('SALE-1', short=False, prefix='S-'),
            'SALE-1',
        )
        self.assertEqual(
            format_sale_number_for_sms('SALE-1', short=True, prefix='S-'),
            'S-1',
        )
        self.assertEqual(
            format_sale_number_for_sms('', short=True, prefix='S-'),
            'S-sale',
        )

        item = SimpleNamespace(
            quantity='bad',
            unit_price=None,
            subtotal=Decimal('0'),
            product=SimpleNamespace(name='Very Long Product Name Here'),
            size=SimpleNamespace(name='L'),
            color=SimpleNamespace(name='Red'),
            variant=None,
        )
        summary = format_sale_items_summary([item, item, item], max_items=1)
        self.assertIn('+2 more', summary)
        self.assertEqual(format_sale_items_summary([]), '')

        self.assertEqual(format_balance_note(0, show_when_zero=False), '')
        self.assertIn('Balance', format_balance_note(10, show_when_zero=False))
        self.assertIn('Balance', format_balance_note(0, show_when_zero=True))
        self.assertEqual(format_payment_ref_note('', include=True), '')
        self.assertEqual(format_payment_ref_note('ABC', include=False), '')
        self.assertIn('Ref', format_payment_ref_note('ABC', include=True))

        self.assertEqual(customer_first_name(None), 'Customer')
        self.assertEqual(customer_greeting_name(None), 'Customer')
        cust = SimpleNamespace(owner_name='', contact_person='', name='')
        self.assertEqual(customer_first_name(cust), 'Customer')
        self.assertEqual(customer_greeting_name(cust), 'Customer')
        cust2 = SimpleNamespace(owner_name='', contact_person='', name='mama shops')
        self.assertEqual(customer_greeting_name(cust2), 'Mama')


class MessagingServicesErrorTests(TestCase):
    def setUp(self):
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        self.user = User.objects.create_user('msg_svc', password='x')

    def tearDown(self):
        set_sms_provider(None)

    def test_serialize_save_reset_errors_and_bulk_fail(self):
        with self.assertRaises(MessagingError):
            serialize_template('missing_key')
        with self.assertRaises(MessagingError):
            save_sms_template('missing_key', 'body')
        with self.assertRaises(MessagingError):
            save_sms_template('debt_reminder', '   ')
        with self.assertRaises(MessagingError):
            save_sms_template('debt_reminder', 'x' * 601)
        with self.assertRaises(MessagingError):
            reset_sms_template('missing_key')

        with self.assertRaises(MessagingError):
            send_debt_reminders(created_by=self.user)

        Customer.objects.create(
            name='Owes', phone='0700111222', wallet_balance=Decimal('-50'),
        )
        self.sms.fail_bulk_next = True
        with self.assertRaises(MessagingError):
            send_debt_reminders(created_by=self.user)


class MessagingExtraGapTests(TestCase):
    """Second-pass gaps: blast errors, template helpers, superuser perms."""

    def setUp(self):
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        self.user = User.objects.create_superuser('msg_su', 'su@test.com', 'x')
        self.customer = Customer.objects.create(
            name='Blast Target', phone='0700123456', is_active=True,
            wallet_balance=Decimal('-20'),
        )

    def tearDown(self):
        set_sms_provider(None)

    def test_superuser_template_edit_and_blast_errors(self):
        from messaging.customer_blast import (
            BlastError,
            build_customer_blast_preview,
            render_blast_sms,
            send_customer_blast,
            send_customer_week_promos,
            build_customer_week_preview,
        )
        from messaging.templates_sms import (
            _item_line_total,
            _item_unit_price,
            render_customer_welcome_sms,
            render_invoice_sms,
            sms_cap_name,
        )
        from messaging.template_catalog import is_customized
        from messaging.services import get_customer_week_template_body

        token = RefreshToken.for_user(self.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

        # superuser _user_can True path
        res = client.get('/api/messaging/templates/')
        self.assertEqual(res.status_code, 200)

        # edit without body when can edit (superuser)
        no_body = client.put('/api/messaging/templates/debt_reminder/', {}, format='json')
        self.assertEqual(no_body.status_code, 400)

        save_sms_template('debt_reminder', 'x' * 10, user=self.user)
        bad_save = client.put(
            '/api/messaging/templates/debt_reminder/',
            {'body': '   '},
            format='json',
        )
        self.assertEqual(bad_save.status_code, 400)

        # debt template put without create denied for non-send? superuser can
        put_ok = client.put(
            '/api/messaging/reminders/debt/template/',
            {'body': 'Hi {name} {amount}'},
            format='json',
        )
        self.assertEqual(put_ok.status_code, 200)

        with self.assertRaises(BlastError):
            render_blast_sms(template_key='nope', customer=self.customer)
        with self.assertRaises(BlastError):
            build_customer_blast_preview(template_key='nope')
        with self.assertRaises(BlastError):
            build_customer_blast_preview(
                template_key=SmsTemplate.KEY_CUSTOMER_WEEK,
                scope='one',
                customer_id=None,
            )
        with self.assertRaises(BlastError):
            send_customer_blast(
                template_key=SmsTemplate.KEY_CUSTOMER_WEEK,
                created_by=self.user,
                customer_ids=[999999],
            )

        self.sms.fail_bulk_next = True
        with self.assertRaises(BlastError):
            send_customer_blast(
                template_key=SmsTemplate.KEY_CUSTOMER_WEEK,
                created_by=self.user,
                scope='one',
                customer_id=self.customer.id,
            )

        # wrappers
        build_customer_week_preview()
        get_customer_week_template_body()
        # send_customer_week_promos success path
        set_sms_provider(FakeSmsProvider())
        send_customer_week_promos(created_by=self.user, scope='one', customer_id=self.customer.id)

        # item price helpers
        priced = SimpleNamespace(unit_price=Decimal('12.5'), quantity=2, subtotal=None)
        self.assertEqual(_item_unit_price(priced), Decimal('12.5'))
        derived = SimpleNamespace(unit_price=None, quantity=2, subtotal=Decimal('20'))
        self.assertEqual(_item_unit_price(derived), Decimal('10.00'))
        empty = SimpleNamespace(unit_price='  ', quantity=0, subtotal='')
        self.assertEqual(_item_unit_price(empty), Decimal('0'))
        line = SimpleNamespace(subtotal='', quantity='x', unit_price=Decimal('3'))
        self.assertEqual(_item_line_total(line), Decimal('0.00'))
        line2 = SimpleNamespace(subtotal=None, quantity=2, unit_price=Decimal('3'))
        self.assertEqual(_item_line_total(line2), Decimal('6.00'))

        self.assertEqual(sms_cap_name('   ', fallback='Z'), 'Z')
        render_invoice_sms(
            customer_name='Ada',
            invoice_no='INV-1',
            amount='100',
            public_token='tok',
            template='Pay {amount} {link}',
        )
        long_welcome = render_customer_welcome_sms(
            name='Customer',
            store_name='Store',
            template='W' * 400,
        )
        self.assertLessEqual(len(long_welcome), 300)

        # is_customized exception path
        with patch(
            'messaging.template_catalog.SmsTemplate.objects.filter',
            side_effect=RuntimeError('db down'),
        ):
            self.assertFalse(is_customized('debt_reminder'))

        # notify exception branches
        with patch(
            'messaging.customer_notify.render_debt_increase_sms',
            side_effect=RuntimeError('x'),
        ):
            self.assertIsNone(notify_customer_debt_increase(self.customer, amount=5))
        with patch(
            'messaging.customer_notify.render_debt_settlement_sms',
            side_effect=RuntimeError('x'),
        ):
            self.assertIsNone(notify_customer_debt_settlement(self.customer, amount=5))
        with patch(
            'messaging.customer_notify.render_customer_welcome_sms',
            side_effect=RuntimeError('x'),
        ):
            self.assertIsNone(notify_customer_welcome(self.customer))

        # dispatch on_commit exception
        msg = MessageOutbox.objects.create(
            to_phone='0700123456', body='hi',
            template_key=MessageOutbox.TEMPLATE_CUSTOMER_WELCOME,
            customer=self.customer,
        )
        with patch(
            'messaging.customer_notify.dispatch_outbox',
            side_effect=RuntimeError('dispatch fail'),
        ):
            from messaging.customer_notify import _queue_customer_sms
            with self.captureOnCommitCallbacks(execute=True):
                _queue_customer_sms(
                    customer=self.customer, body='hi',
                    template_key=MessageOutbox.TEMPLATE_CUSTOMER_WELCOME,
                )

        # BlastError str
        err = BlastError({'a': 1})
        self.assertIn('a', str(err.detail))

        # views blast BlastError
        with patch(
            'messaging.customer_blast.build_customer_blast_preview',
            side_effect=BlastError({'x': 1}),
        ):
            bad_prev = client.post(
                '/api/messaging/blast/preview/',
                {'template_key': SmsTemplate.KEY_CUSTOMER_WEEK},
                format='json',
            )
            self.assertEqual(bad_prev.status_code, 400)
            bad_week = client.post(
                '/api/messaging/promos/customer-week/preview/',
                {},
                format='json',
            )
            self.assertEqual(bad_week.status_code, 400)

        with patch(
            'messaging.customer_blast.send_customer_blast',
            side_effect=BlastError({'x': 1}),
        ):
            bad_send = client.post(
                '/api/messaging/blast/send/',
                {'template_key': SmsTemplate.KEY_CUSTOMER_WEEK, 'scope': 'one',
                 'customer_id': self.customer.id},
                format='json',
            )
            self.assertEqual(bad_send.status_code, 400)
            bad_week_send = client.post(
                '/api/messaging/promos/customer-week/send/',
                {'scope': 'one', 'customer_id': self.customer.id},
                format='json',
            )
            self.assertEqual(bad_week_send.status_code, 400)

        # debt template put denied for authenticated user without send perm
        # (profile-less user)
        bare = User.objects.create_user('bare_msg', password='x')
        # no profile → False
        from messaging.views import _user_can
        self.assertFalse(_user_can(bare, 'messaging', 'view'))
        self.assertFalse(_user_can(None, 'messaging', 'view'))
        self.assertTrue(_user_can(self.user, 'messaging', 'view'))

        # providers build default + get_sms_provider cache
        from messaging import providers as p
        p._provider = None
        set_sms_provider(None)
        with override_settings(SMS_LIVE_DISABLED=False, SMS_PROVIDER=''):
            get_sms_provider()
        with override_settings(SMS_LIVE_DISABLED=False, SMS_PROVIDER='none'):
            p._provider = None
            build_sms_provider_from_settings()

        # HTTPError with unreadable body
        http_err = urllib.error.HTTPError('http://x', 500, 'err', hdrs=None, fp=None)
        with patch.object(http_err, 'read', side_effect=OSError('x')):
            with patch('messaging.providers.urllib.request.urlopen', side_effect=http_err):
                data, err = providers_mod._mobilesasa_post('http://x', 't', {}, 1)
                self.assertIsNone(data)

        from messaging.services import build_customer_week_preview as svc_prev
        from messaging.services import send_customer_week_promos as svc_send
        svc_prev(scope='one', customer_id=self.customer.id)
