"""Audit trail must record web vs mobile without blocking business writes."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import PermissionDenied

from accounts.models import AuditLog
from config.exceptions import custom_exception_handler
from utils.audit import log_audit
from utils.tests.api_test_base import SuperAdminAPITestCase


class AuditClientChannelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('chan_user', password='x')
        self.factory = RequestFactory()

    def test_log_audit_records_web_from_header(self):
        request = self.factory.post('/api/sales/')
        request.user = self.user
        request.META['HTTP_X_CLIENT_CHANNEL'] = 'web'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        log_audit(request, AuditLog.ACTION_CREATE, self.user, module='users')
        row = AuditLog.objects.latest('id')
        self.assertEqual(row.client_channel, 'web')
        self.assertEqual(row.changes.get('client_channel'), 'web')

    def test_log_audit_records_mobile_from_header(self):
        request = self.factory.post('/api/sales/')
        request.user = self.user
        request.META['HTTP_X_CLIENT_CHANNEL'] = 'mobile'
        request.META['HTTP_USER_AGENT'] = 'Dart/3.0 (dart:io)'
        log_audit(request, 'checkout', self.user, module='sales', changes={'total': '10'})
        row = AuditLog.objects.latest('id')
        self.assertEqual(row.client_channel, 'mobile')
        self.assertEqual(row.changes.get('total'), '10')
        self.assertEqual(row.changes.get('client_channel'), 'mobile')

    def test_log_audit_failure_never_raises(self):
        request = self.factory.post('/api/sales/')
        request.user = self.user
        with patch('accounts.models.AuditLog.objects.create', side_effect=RuntimeError('db down')):
            log_audit(request, AuditLog.ACTION_UPDATE, self.user, module='users')
        # No exception bubbled; business caller continues.


class AuditPermissionDeniedHandlerTests(TestCase):
    def test_authenticated_403_writes_audit_row(self):
        user = User.objects.create_user('denied_user', password='x')
        factory = RequestFactory()
        request = factory.get('/api/payroll/settings/')
        request.user = user
        request.META['HTTP_X_CLIENT_CHANNEL'] = 'mobile'

        class DummyView:
            audit_module = 'payroll'
            action = 'retrieve'

        before = AuditLog.objects.filter(action=AuditLog.ACTION_PERMISSION_DENIED).count()
        response = custom_exception_handler(
            PermissionDenied('nope'),
            {'request': request, 'view': DummyView()},
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.ACTION_PERMISSION_DENIED).count(),
            before + 1,
        )
        row = AuditLog.objects.filter(action=AuditLog.ACTION_PERMISSION_DENIED).latest('id')
        self.assertEqual(row.client_channel, 'mobile')
        self.assertEqual(row.module, 'payroll')


class AuditClientChannelAPITests(SuperAdminAPITestCase):
    def test_filter_and_serialize_client_channel(self):
        AuditLog.objects.create(
            user=self.admin,
            username_snapshot='admin',
            action='checkout',
            module='sales',
            client_channel='mobile',
            object_repr='SALE-M',
            changes={'total': '50'},
        )
        AuditLog.objects.create(
            user=self.admin,
            username_snapshot='admin',
            action='checkout',
            module='sales',
            client_channel='web',
            object_repr='SALE-W',
            changes={'total': '60'},
        )
        res = self.client.get('/api/accounts/audit-logs/', {'client_channel': 'mobile'})
        self.assertEqual(res.status_code, 200)
        rows = res.data.get('results', res.data)
        self.assertTrue(all(r['client_channel'] == 'mobile' for r in rows))
        self.assertTrue(any(r['object_repr'] == 'SALE-M' for r in rows))

        facets = self.client.get('/api/accounts/audit-logs/facets/')
        self.assertEqual(facets.status_code, 200)
        self.assertIn('client_channels', facets.data)
