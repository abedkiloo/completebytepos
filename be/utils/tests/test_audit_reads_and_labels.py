"""Unit, module, corrected, security, and stress tests for audit labels + reads."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import AuditLog
from products.models import Category, Product
from sales.models import Customer
from settings.models import ModuleFeature, ModuleSettings
from utils.audit_helpers import audit_reads_enabled, log_sensitive_read
from utils.audit_labels import action_display_label, module_display_label
from utils.tests.api_test_base import ManagerAPITestCase


class AuditLabelUnitTests(SimpleTestCase):
    def test_known_and_view_labels(self):
        self.assertEqual(action_display_label('checkout'), 'Sale money posted')
        self.assertEqual(action_display_label('view'), 'Opened / viewed')
        self.assertEqual(action_display_label('call_marked'), 'Call marked')

    def test_never_bare_number(self):
        self.assertEqual(action_display_label('42'), 'Action 42')
        self.assertEqual(action_display_label(''), '—')

    def test_snake_case_fallback(self):
        self.assertEqual(action_display_label('custom_event_xyz'), 'Custom Event Xyz')

    def test_module_labels(self):
        self.assertEqual(module_display_label('sales'), 'Sales / POS')
        self.assertEqual(module_display_label(''), '—')


class AuditReadHelperTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('audit_reader', password='x')
        self.factory = APIRequestFactory()
        ModuleSettings.objects.update_or_create(
            module_name='settings',
            defaults={'is_enabled': True, 'description': 'settings'},
        )
        mod = ModuleSettings.objects.get(module_name='settings')
        ModuleFeature.objects.update_or_create(
            module=mod,
            feature_key='audit_sensitive_reads',
            defaults={
                'feature_name': 'Audit record opens',
                'is_enabled': True,
            },
        )

    def _auth_request(self, path='/api/x/'):
        from rest_framework.request import Request

        django_req = self.factory.get(path)
        force_authenticate(django_req, user=self.user)
        return Request(django_req)

    def test_log_sensitive_read_writes_view_row(self):
        from unittest.mock import patch

        self.assertEqual(AuditLog.ACTION_VIEW, 'view')
        customer = Customer.objects.create(name='Audit Shop', phone='0711000001')
        request = self._auth_request(f'/api/sales/customers/{customer.id}/')
        self.assertTrue(request.user.is_authenticated)
        before = AuditLog.objects.filter(action='view').count()
        with patch(
            'utils.audit_helpers.audit_reads_enabled', return_value=True
        ):
            log_sensitive_read(request, customer, module='customers', purpose='detail')
        after = AuditLog.objects.filter(action='view').count()
        self.assertEqual(after, before + 1)
        row = AuditLog.objects.filter(action='view').latest('id')
        self.assertEqual(row.module, 'customers')
        self.assertEqual(row.changes.get('kind'), 'read')
        self.assertNotIn('password', str(row.changes).lower())
        self.assertNotIn('phone', str(row.changes).lower())

    def test_dedupe_skips_second_view(self):
        from unittest.mock import patch

        customer = Customer.objects.create(name='Dedupe Shop', phone='0711000002')
        request = self._auth_request(f'/api/sales/customers/{customer.id}/')
        with patch(
            'utils.audit_helpers.audit_reads_enabled', return_value=True
        ):
            log_sensitive_read(request, customer, module='customers')
            log_sensitive_read(request, customer, module='customers')
        self.assertEqual(
            AuditLog.objects.filter(
                action='view',
                object_id=str(customer.id),
                user=self.user,
            ).count(),
            1,
        )

    def test_feature_off_skips_read(self):
        mod = ModuleSettings.objects.get(module_name='settings')
        ModuleFeature.objects.filter(
            module=mod, feature_key='audit_sensitive_reads'
        ).update(is_enabled=False)
        cache.clear()
        self.assertFalse(audit_reads_enabled())
        customer = Customer.objects.create(name='Off Shop', phone='0711000003')
        request = self._auth_request('/api/sales/customers/1/')
        before = AuditLog.objects.count()
        log_sensitive_read(request, customer, module='customers')
        self.assertEqual(AuditLog.objects.count(), before)


class AuditReadApiCorrectedTests(ManagerAPITestCase):
    """Corrected: opening a customer detail leaves a named view audit row."""

    def setUp(self):
        super().setUp()
        cache.clear()
        ModuleSettings.objects.update_or_create(
            module_name='settings',
            defaults={'is_enabled': True, 'description': 'settings'},
        )
        mod = ModuleSettings.objects.get(module_name='settings')
        ModuleFeature.objects.update_or_create(
            module=mod,
            feature_key='audit_sensitive_reads',
            defaults={
                'feature_name': 'Audit record opens',
                'is_enabled': True,
            },
        )
        self.customer = Customer.objects.create(
            name='Viewed Customer',
            phone='0711555000',
            is_active=True,
        )

    def test_customer_retrieve_writes_view_audit(self):
        before = AuditLog.objects.filter(action='view').count()
        resp = self.client.get(f'/api/sales/customers/{self.customer.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(AuditLog.objects.filter(action='view').count(), before + 1)

    def test_audit_list_exposes_action_display(self):
        request = self.client.get(f'/api/sales/customers/{self.customer.id}/')
        self.assertEqual(request.status_code, status.HTTP_200_OK)
        # Manager may or may not see audit log; create a row and serialize via API if allowed
        row = AuditLog.objects.filter(action='view').order_by('-id').first()
        self.assertIsNotNone(row)
        from accounts.serializers import AuditLogSerializer

        data = AuditLogSerializer(row).data
        self.assertEqual(data['action'], 'view')
        self.assertEqual(data['action_display'], 'Opened / viewed')
        self.assertIn('module_display', data)

    def test_product_retrieve_does_not_spam_view(self):
        cat = Category.objects.create(name='Audit Cat', is_active=True)
        product = Product.objects.create(
            name='No View Log',
            sku='NVL-1',
            category=cat,
            price=10,
            cost=5,
            stock_quantity=1,
            is_active=True,
        )
        before = AuditLog.objects.filter(action='view').count()
        resp = self.client.get(f'/api/products/{product.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(AuditLog.objects.filter(action='view').count(), before)


class AuditReadStressTests(SimpleTestCase):
    def test_label_lookup_many(self):
        for i in range(500):
            label = action_display_label('checkout' if i % 2 == 0 else f'event_{i}')
            self.assertTrue(len(label) >= 1)
            self.assertFalse(label.isdigit())
