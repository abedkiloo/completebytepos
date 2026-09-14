"""Debt reminder + SMS provider coverage."""

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ensure_permissions, sync_default_roles
from messaging.models import MessageOutbox
from messaging.providers import (
    AfricasTalkingSmsProvider,
    FakeSmsProvider,
    set_sms_provider,
)
from messaging.services import queue_debt_reminders
from messaging.templates_sms import render_debt_reminder_sms
from sales.models import Customer


class MessagingAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.user = User.objects.create_user('msg_user', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.debtor = Customer.objects.create(
            name='Owes', phone='0700111222', wallet_balance=Decimal('-250.00'),
        )
        Customer.objects.create(
            name='Credit', phone='0700333444', wallet_balance=Decimal('10.00'),
        )
        Customer.objects.create(
            name='NoPhone', phone='', wallet_balance=Decimal('-10.00'),
        )

    def setUp(self):
        self.sms = FakeSmsProvider()
        set_sms_provider(self.sms)
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_debt_reminders_api(self):
        res = self.client.post('/api/messaging/reminders/debt/')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['queued'], 1)
        self.assertEqual(len(self.sms.sent), 1)
        self.assertIn('Reminder', self.sms.sent[0]['body'])
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=MessageOutbox.TEMPLATE_DEBT_REMINDER,
                status=MessageOutbox.STATUS_SENT,
            ).count(),
            1,
        )

    def test_reminder_template_and_at_provider(self):
        body = render_debt_reminder_sms(
            customer_name='Owes',
            amount='250.00',
            public_token='debt-1',
        )
        self.assertIn('Owes', body)
        self.assertIn('250.00', body)
        at = AfricasTalkingSmsProvider(api_key='', username='')
        self.assertFalse(at.send(to='2547', body='x').ok)
        at2 = AfricasTalkingSmsProvider(api_key='k', username='u')
        self.assertFalse(at2.send(to='2547', body='x').ok)

    def test_sms_failure_path(self):
        self.sms.fail_next = True
        queued = queue_debt_reminders(created_by=self.user)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].status, MessageOutbox.STATUS_FAILED)
        self.assertIn('Message', str(queued[0]))
