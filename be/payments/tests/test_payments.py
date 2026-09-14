"""PaymentIntent STK + callback idempotency + SMS on paid."""

import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from messaging.models import MessageOutbox
from messaging.providers import FakeSmsProvider, set_sms_provider
from messaging.templates_sms import INVOICE_TEMPLATE, render_invoice_sms
from payments.daraja import FakeDarajaClient, set_daraja_client
from payments.models import PaymentIntent
from payments.services import (
    PaymentTransitionError,
    create_intent,
    initiate_stk,
    normalize_phone,
    process_callback,
    reconcile_query,
)
from sales.models import Customer


class PaymentsAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('pay_user', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.customer = Customer.objects.create(
            name='Pay Cust', phone='0712345678', wallet_balance=Decimal('-500'),
        )

    def setUp(self):
        self.daraja = FakeDarajaClient(auto_succeed=True)
        set_daraja_client(self.daraja)
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone('0712345678'), '254712345678')
        with self.assertRaises(PaymentTransitionError):
            normalize_phone('123')

    def test_create_stk_callback_idempotent_and_sms(self):
        res = self.client.post(
            '/api/payments/intents/',
            {
                'amount': '150.00',
                'phone': '0712345678',
                'purpose': 'pos',
                'customer_id': self.customer.id,
                'client_uuid': str(uuid.uuid4()),
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        intent_id = res.data['id']
        self.assertEqual(res.data['status'], 'created')

        stk = self.client.post(f'/api/payments/intents/{intent_id}/stk/')
        self.assertEqual(stk.status_code, status.HTTP_200_OK, stk.data)
        self.assertEqual(stk.data['status'], 'prompted')
        checkout = stk.data['checkout_request_id']
        self.assertTrue(checkout)

        # Sandbox success via callback
        cb = self.client.post(
            '/api/payments/daraja/callback/',
            {
                'Body': {
                    'stkCallback': {
                        'CheckoutRequestID': checkout,
                        'ResultCode': 0,
                        'ResultDesc': 'Success',
                        'CallbackMetadata': {
                            'Item': [
                                {'Name': 'MpesaReceiptNumber', 'Value': 'ABC123'},
                            ],
                        },
                    },
                },
            },
            format='json',
        )
        self.assertEqual(cb.status_code, status.HTTP_200_OK, cb.data)

        poll = self.client.get(f'/api/payments/intents/{intent_id}/')
        self.assertEqual(poll.data['status'], 'paid')
        self.assertEqual(poll.data['mpesa_receipt'], 'ABC123')
        self.assertTrue(poll.data['sms_queued'])
        self.assertTrue(poll.data['sms_sent'])
        self.assertEqual(len(self.sms.sent), 1)
        self.assertIn('Invoice', self.sms.sent[0]['body'])

        # Duplicate callback is idempotent
        cb2 = self.client.post(
            '/api/payments/daraja/callback/',
            {
                'Body': {
                    'stkCallback': {
                        'CheckoutRequestID': checkout,
                        'ResultCode': 0,
                        'CallbackMetadata': {'Item': []},
                    },
                },
            },
            format='json',
        )
        self.assertEqual(cb2.status_code, status.HTTP_200_OK)
        self.assertEqual(MessageOutbox.objects.filter(payment_intent_id=intent_id).count(), 1)

        pub = self.client.get(f'/api/public/invoices/{poll.data["invoice_link_token"]}/')
        self.assertEqual(pub.status_code, status.HTTP_200_OK)
        self.assertEqual(pub.data['status'], 'paid')
        self.assertIn('brand_blurb', pub.data)

    def test_query_reconcile(self):
        intent = create_intent(
            amount='10', phone='0711111111', created_by=self.user,
        )
        initiate_stk(intent)
        intent.refresh_from_db()
        reconciled = reconcile_query(intent)
        self.assertEqual(reconciled.status, PaymentIntent.STATUS_PAID)

        q = self.client.post(f'/api/payments/intents/{intent.id}/query/')
        self.assertEqual(q.status_code, status.HTTP_200_OK)
        self.assertEqual(q.data['status'], 'paid')

    def test_callback_failure_and_duplicate_query(self):
        intent = create_intent(amount='20', phone='0722222222', created_by=self.user)
        initiate_stk(intent)
        intent.refresh_from_db()
        self.daraja.mark_failed(intent.checkout_request_id, 'User cancelled')
        failed = reconcile_query(intent)
        self.assertEqual(failed.status, PaymentIntent.STATUS_FAILED)

        cb = self.client.post(
            '/api/payments/daraja/callback/',
            {
                'Body': {
                    'stkCallback': {
                        'CheckoutRequestID': intent.checkout_request_id,
                        'ResultCode': 1032,
                        'ResultDesc': 'Cancelled',
                    },
                },
            },
            format='json',
        )
        # already failed terminal — still 200
        self.assertEqual(cb.status_code, status.HTTP_200_OK)

    def test_sms_template_snapshot(self):
        body = render_invoice_sms(
            customer_name='Ada',
            invoice_no='INV-TEST01',
            amount='99.00',
            public_token='tok123',
            brand_blurb='Brand here.',
        )
        self.assertEqual(
            body,
            INVOICE_TEMPLATE.format(
                customer_name='Ada',
                brand_blurb='Brand here.',
                invoice_no='INV-TEST01',
                amount='99.00',
                link='https://example.com/i/tok123',
            ),
        )
        self.assertIn('Ada', body)
        self.assertIn('INV-TEST01', body)
        self.assertIn('tok123', body)

    def test_invalid_amount_and_stk_from_paid(self):
        bad = self.client.post(
            '/api/payments/intents/',
            {'amount': '0', 'phone': '0700000000'},
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        intent = create_intent(amount='5', phone='0700000000', created_by=self.user)
        initiate_stk(intent)
        intent.refresh_from_db()
        reconcile_query(intent)
        intent.refresh_from_db()
        with self.assertRaises(PaymentTransitionError):
            initiate_stk(intent)

    def test_str_helpers(self):
        intent = create_intent(amount='1', phone='0733333333', created_by=self.user)
        self.assertIn('PaymentIntent', str(intent))
        self.assertFalse(intent.is_terminal)
