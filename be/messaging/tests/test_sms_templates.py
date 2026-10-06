"""Editable SMS template catalog API."""

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from messaging.models import SmsTemplate
from messaging.services import save_sms_template
from messaging.templates_sms import render_sale_completed_sms


class SmsTemplatesAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('sms_tpl', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )

    def setUp(self):
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_list_includes_sale_and_debt(self):
        res = self.client.get('/api/messaging/templates/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        keys = {r['key'] for r in res.data['results']}
        self.assertIn('sale_completed', keys)
        self.assertIn('debt_settlement', keys)
        self.assertIn('debt_reminder', keys)
        self.assertIn('invoice_receipt', keys)

    def test_save_sale_template_and_render(self):
        body = 'Hi {first_name}! Sale {sale_number} done. Paid {paid}.{balance_note}'
        res = self.client.patch(
            '/api/messaging/templates/sale_completed/',
            {'body': body},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertTrue(res.data['is_customized'])
        self.assertTrue(
            SmsTemplate.objects.filter(key='sale_completed').exists()
        )
        text = render_sale_completed_sms(
            first_name='Jane',
            sale_number='SALE-9',
            total='100',
            paid='100',
            balance_owed=0,
        )
        self.assertEqual(text, 'Hi Jane! Sale SALE-9 done. Paid 100.')

    def test_reset_restores_default(self):
        save_sms_template(
            'sale_completed',
            'Custom {first_name} only.',
            user=self.user,
        )
        res = self.client.delete('/api/messaging/templates/sale_completed/')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertFalse(res.data['is_customized'])
        self.assertFalse(
            SmsTemplate.objects.filter(key='sale_completed').exists()
        )
