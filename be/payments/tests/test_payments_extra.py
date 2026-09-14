"""Extra branches for payments coverage gate."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from messaging.providers import FakeSmsProvider, get_sms_provider, set_sms_provider
from payments.config import daraja_config
from payments.daraja import FakeDarajaClient, get_daraja_client, set_daraja_client
from payments.models import PaymentIntent
from payments.services import (
    PaymentTransitionError,
    create_intent,
    dispatch_message,
    initiate_stk,
    mark_failed,
    mark_paid,
    process_callback,
    queue_invoice_sms,
    reconcile_query,
)
from sales.models import Customer


class PaymentsExtraTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('pay_x', password='x')
        UserProfile.objects.create(
            user=cls.user, role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES), is_active=True,
        )
        cls.su = User.objects.create_superuser('pay_su', 's@x.com', 'x')

    def setUp(self):
        self.daraja = FakeDarajaClient(auto_succeed=False)
        set_daraja_client(self.daraja)
        set_sms_provider(FakeSmsProvider())
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_config_getters_and_processing_query(self):
        self.assertIn('shortcode', daraja_config())
        set_daraja_client(None)
        self.assertIsInstance(get_daraja_client(), FakeDarajaClient)
        set_sms_provider(None)
        self.assertIsInstance(get_sms_provider(), FakeSmsProvider)

        set_daraja_client(self.daraja)
        intent = create_intent(amount='3', phone='0744444444', created_by=self.user)
        initiate_stk(intent)
        intent.refresh_from_db()
        # still processing
        same = reconcile_query(intent)
        self.assertEqual(same.status, PaymentIntent.STATUS_PROMPTED)

    def test_callback_errors_and_stk_api_errors(self):
        with self.assertRaises(PaymentTransitionError):
            process_callback({'Body': {'stkCallback': {}}})
        with self.assertRaises(PaymentTransitionError):
            process_callback({
                'Body': {'stkCallback': {'CheckoutRequestID': 'missing'}},
            })

        intent = create_intent(amount='4', phone='0755555555', created_by=self.user)
        initiate_stk(intent)
        intent.refresh_from_db()
        mark_paid(intent, mpesa_receipt='R1')
        intent.refresh_from_db()
        again = mark_paid(intent, mpesa_receipt='R2')
        self.assertEqual(again.mpesa_receipt, 'R1')
        queue_invoice_sms(intent)  # already queued

        paid = create_intent(amount='5', phone='0766666666', created_by=self.user)
        initiate_stk(paid)
        paid.refresh_from_db()
        mark_paid(paid, mpesa_receipt='X')
        with self.assertRaises(PaymentTransitionError):
            initiate_stk(paid)

        bad_stk = self.client.post('/api/payments/intents/99999/stk/')
        self.assertEqual(bad_stk.status_code, status.HTTP_404_NOT_FOUND)

        intent2 = create_intent(amount='6', phone='0777777777', created_by=self.user)
        # query without checkout
        with self.assertRaises(PaymentTransitionError):
            reconcile_query(intent2)

        mark_failed(intent2, reason='x')
        term = create_intent(amount='7', phone='0788888888', created_by=self.user)
        initiate_stk(term)
        term.refresh_from_db()
        mark_paid(term, mpesa_receipt='Z')
        mark_failed(term, reason='ignored')  # terminal non-failed

    def test_create_unknown_customer_and_superuser_list(self):
        bad = self.client.post(
            '/api/payments/intents/',
            {'amount': '1', 'phone': '0700000001', 'customer_id': 999999},
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        intent = create_intent(amount='1', phone='0700000002', created_by=self.user)
        initiate_stk(intent)
        # STK again while prompted returns same
        initiate_stk(intent)

        token = RefreshToken.for_user(self.su)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        # retrieve via viewset list not registered — retrieve ok as su
        # create as su then query failure path on API
        res = self.client.post(
            '/api/payments/intents/',
            {'amount': '8', 'phone': '0799999999'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        iid = res.data['id']
        self.client.post(f'/api/payments/intents/{iid}/stk/')
        # force API query while processing
        q = self.client.post(f'/api/payments/intents/{iid}/query/')
        self.assertEqual(q.status_code, status.HTTP_200_OK)

    def test_sms_dispatch_failure(self):
        sms = FakeSmsProvider(fail_next=True)
        set_sms_provider(sms)
        intent = create_intent(amount='9', phone='0710000000', created_by=self.user)
        initiate_stk(intent)
        intent.refresh_from_db()
        self.daraja.force_result[intent.checkout_request_id] = (
            __import__('payments.daraja', fromlist=['StkQueryResult']).StkQueryResult(
                result_code='0', result_desc='ok', mpesa_receipt='M1',
            )
        )
        reconcile_query(intent)
        intent.refresh_from_db()
        # first SMS failed then we can retry dispatch
        msg = intent.messages.first()
        self.assertEqual(msg.status, 'failed')
        sms.fail_next = False
        dispatch_message(msg)
        msg.refresh_from_db()
        self.assertEqual(msg.status, 'sent')

    def test_callback_api_error_response(self):
        res = self.client.post('/api/payments/daraja/callback/', {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        intent = create_intent(amount='1', phone='0701111111', created_by=self.user)
        # query API without stk
        q = self.client.post(f'/api/payments/intents/{intent.id}/query/')
        self.assertEqual(q.status_code, status.HTTP_400_BAD_REQUEST)
        # stk on created works
        self.client.post(f'/api/payments/intents/{intent.id}/stk/')
        # stk on paid fails via API
        intent.refresh_from_db()
        mark_paid(intent, mpesa_receipt='P')
        bad = self.client.post(f'/api/payments/intents/{intent.id}/stk/')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
