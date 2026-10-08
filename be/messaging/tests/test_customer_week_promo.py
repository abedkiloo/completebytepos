"""Customer SMS blast: all valid phones or one, any template."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from messaging.models import MessageOutbox, SmsTemplate
from messaging.providers import FakeSmsProvider, set_sms_provider
from messaging.services import build_customer_week_preview
from sales.models import Customer


class CustomerBlastAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('promo_sms', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.duka = Customer.objects.create(
            name='Mama Mboga [west]',
            owner_name='Grace Achieng',
            phone='0700111222',
            is_active=True,
            wallet_balance=Decimal('-500.00'),
        )
        cls.person = Customer.objects.create(
            name='mwangi wa jogoo',
            owner_name='Mwangi',
            phone='0700333444',
            is_active=True,
            wallet_balance=Decimal('0.00'),
        )
        Customer.objects.create(
            name='No Phone Duka',
            phone='',
            is_active=True,
        )
        Customer.objects.create(
            name='Bad Phone Duka',
            phone='123',
            is_active=True,
        )
        Customer.objects.create(
            name='Inactive Duka',
            phone='0700555666',
            is_active=False,
        )

    def setUp(self):
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def tearDown(self):
        set_sms_provider(None)

    def test_preview_lists_active_customers_with_valid_phones(self):
        res = self.client.get('/api/messaging/promos/customer-week/preview/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data['count'], 2)
        self.assertEqual(res.data['skipped_no_phone'], 1)
        self.assertEqual(res.data['skipped_invalid_phone'], 1)
        names = {r['greeting_name'] for r in res.data['recipients']}
        self.assertIn('Mama', names)
        self.assertIn('Mwangi', names)
        mama = next(r for r in res.data['recipients'] if r['customer_id'] == self.duka.pk)
        self.assertIn('Customer Week', mama['message'])
        self.assertNotIn('[west]', mama['message'])

    def test_blast_one_customer(self):
        res = self.client.post(
            '/api/messaging/blast/preview/',
            {
                'template_key': SmsTemplate.KEY_CUSTOMER_WEEK,
                'scope': 'one',
                'customer_id': self.person.pk,
                'offer': 'Soap deal.',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['recipients'][0]['customer_id'], self.person.pk)
        self.assertIn('Soap deal.', res.data['recipients'][0]['message'])

        send = self.client.post(
            '/api/messaging/blast/send/',
            {
                'template_key': SmsTemplate.KEY_CUSTOMER_WEEK,
                'scope': 'one',
                'customer_id': self.person.pk,
                'offer': 'Soap deal.',
            },
            format='json',
        )
        self.assertEqual(send.status_code, status.HTTP_201_CREATED, send.data)
        self.assertEqual(send.data['queued'], 1)
        self.assertEqual(len(self.sms.sent), 1)
        self.assertIn('Mwangi', self.sms.sent[0]['body'])

    def test_debt_collection_only_includes_debtors(self):
        preview = self.client.post(
            '/api/messaging/blast/preview/',
            {
                'template_key': SmsTemplate.KEY_DEBT_REMINDER,
                'scope': 'all',
            },
            format='json',
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertTrue(preview.data['debt_only'])
        ids = {r['customer_id'] for r in preview.data['recipients']}
        self.assertIn(self.duka.pk, ids)
        self.assertNotIn(self.person.pk, ids)

        res = self.client.post(
            '/api/messaging/blast/send/',
            {
                'template_key': SmsTemplate.KEY_DEBT_REMINDER,
                'scope': 'all',
                'template': 'Hi {name}, balance KES {amount} at {store_name}.',
                'customer_ids': [self.duka.pk, self.person.pk],
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['queued'], 1)
        self.assertIn('Mama', self.sms.sent[0]['body'])
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=SmsTemplate.KEY_DEBT_REMINDER,
                status=MessageOutbox.STATUS_SENT,
            ).count(),
            1,
        )

    def test_preview_applies_offer_and_template(self):
        preview = build_customer_week_preview(
            template='Karibu {name} at {store_name}. {offer}Asante.',
            offer='Soap specials this week!',
            customer_ids=[self.duka.pk],
        )
        self.assertEqual(preview['count'], 1)
        msg = preview['recipients'][0]['message']
        self.assertIn('Karibu Mama', msg)
        self.assertIn('Soap specials this week!', msg)

    def test_send_bulk_and_save_template(self):
        body = 'Hi {name}, Customer Week at {store_name}! {offer}Karibu.'
        res = self.client.post(
            '/api/messaging/promos/customer-week/send/',
            {
                'template': body,
                'offer': 'Fast movers on offer.',
                'customer_ids': [self.duka.pk, self.person.pk],
                'save_template': True,
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['queued'], 2)
        self.assertEqual(len(self.sms.bulk_sent), 1)
        self.assertEqual(len(self.sms.sent), 2)
        self.assertTrue(
            SmsTemplate.objects.filter(key=SmsTemplate.KEY_CUSTOMER_WEEK).exists()
        )
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=MessageOutbox.TEMPLATE_CUSTOMER_WEEK,
                status=MessageOutbox.STATUS_SENT,
            ).count(),
            2,
        )
        bodies = [m['body'] for m in self.sms.sent]
        self.assertTrue(any('Mama' in b for b in bodies))
        self.assertTrue(any('Mwangi' in b for b in bodies))
        self.assertTrue(all('Fast movers on offer.' in b for b in bodies))

    def test_send_requires_selection_when_ids_empty(self):
        res = self.client.post(
            '/api/messaging/promos/customer-week/send/',
            {'customer_ids': []},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
