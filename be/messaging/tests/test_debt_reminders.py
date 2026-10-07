"""Debt reminder preview + personalized bulk send."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from messaging.models import MessageOutbox, SmsTemplate
from messaging.providers import FakeSmsProvider, MobileSasaSmsProvider, set_sms_provider
from messaging.services import build_debt_reminder_preview
from messaging.templates_sms import customer_greeting_name, render_debt_collection_reminder
from sales.models import Customer


class GreetingNameTests(APITestCase):
    def test_prefers_duka_name(self):
        c = Customer(name='Sunrise Duka', owner_name='Jane Wambui')
        self.assertEqual(customer_greeting_name(c), 'Sunrise')

    def test_falls_back_to_first_name(self):
        c = Customer(name='', owner_name='Jane Wambui')
        self.assertEqual(customer_greeting_name(c), 'Jane')


class DebtReminderBulkAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('debt_sms', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.duka = Customer.objects.create(
            name='Mama Mboga',
            owner_name='Grace Achieng',
            phone='0700111222',
            wallet_balance=Decimal('-500.00'),
        )
        cls.person = Customer.objects.create(
            name='',
            owner_name='Peter Otieno',
            phone='0700333444',
            wallet_balance=Decimal('-200.00'),
        )
        Customer.objects.create(
            name='No Phone Duka',
            phone='',
            wallet_balance=Decimal('-50.00'),
        )

    def setUp(self):
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def tearDown(self):
        set_sms_provider(None)

    def test_preview_lists_debtors_with_rendered_messages(self):
        res = self.client.get('/api/messaging/reminders/debt/preview/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data['count'], 2)
        self.assertEqual(res.data['skipped_no_phone'], 1)
        names = {r['greeting_name'] for r in res.data['recipients']}
        self.assertIn('Mama', names)
        self.assertIn('Peter', names)
        mama = next(r for r in res.data['recipients'] if r['customer_id'] == self.duka.pk)
        self.assertIn('Mama', mama['message'])
        self.assertIn('500', mama['message'])

    def test_save_template_and_send_bulk(self):
        body = 'Hi {name}, please clear KES {amount} with {store_name}. Asante.'
        save = self.client.patch(
            '/api/messaging/reminders/debt/template/',
            {'body': body},
            format='json',
        )
        self.assertEqual(save.status_code, status.HTTP_200_OK, save.data)
        self.assertTrue(
            SmsTemplate.objects.filter(key=SmsTemplate.KEY_DEBT_REMINDER).exists()
        )

        res = self.client.post(
            '/api/messaging/reminders/debt/send/',
            {
                'template': body,
                'customer_ids': [self.duka.pk, self.person.pk],
                'save_template': True,
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['queued'], 2)
        self.assertEqual(len(self.sms.bulk_sent), 1)
        self.assertEqual(len(self.sms.sent), 2)
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=MessageOutbox.TEMPLATE_DEBT_REMINDER,
                status=MessageOutbox.STATUS_SENT,
            ).count(),
            2,
        )

    def test_send_requires_selection_when_ids_empty(self):
        res = self.client.post(
            '/api/messaging/reminders/debt/send/',
            {'customer_ids': []},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_service_preview_uses_custom_template(self):
        preview = build_debt_reminder_preview(
            template='Karibu {name} — {amount} due at {store_name}.',
            customer_ids=[self.duka.pk],
        )
        self.assertEqual(preview['count'], 1)
        self.assertIn('Mama', preview['recipients'][0]['message'])
        self.assertIn('500', preview['recipients'][0]['message'])
        self.assertNotIn('Mboga', preview['recipients'][0]['message'])


class MobileSasaBulkProviderTests(APITestCase):
    @patch('messaging.providers.urllib.request.urlopen')
    def test_bulk_personalized_posts_message_body(self, mock_urlopen):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return (
                    b'{"status":true,"responseCode":"0200","message":"Accepted",'
                    b'"bulkId":"bulk-99"}'
                )

        mock_urlopen.return_value = _Resp()
        p = MobileSasaSmsProvider(api_token='mbs_x', sender_id='SHOP')
        result = p.send_bulk_personalized(messages=[
            {'phone': '0700111222', 'message': 'Hi Mama Mboga, KES 500'},
            {'phone': '0700333444', 'message': 'Hi Peter, KES 200'},
        ])
        self.assertTrue(result.ok)
        self.assertEqual(result.provider_ref, 'bulk-99')
        self.assertEqual(result.accepted_count, 2)

    def test_render_collection_message(self):
        text = render_debt_collection_reminder(
            template='Hi {name}, balance KES {amount} at {store_name}.',
            name='Sunrise',
            amount='1200.50',
            store_name='Omuwenga',
        )
        self.assertEqual(text, 'Hi Sunrise, balance KES 1200.5 at Omuwenga.')
