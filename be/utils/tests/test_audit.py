"""Coverage for utils.audit helpers."""

from decimal import Decimal
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from accounts.models import AuditLog
from products.models import Category, Product
from utils.audit import _client_ip, diff_instance, log_audit


class AuditModuleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('audit_mod', password='x')
        self.factory = RequestFactory()

    def test_client_ip_forwarded_and_remote(self):
        req = self.factory.get('/')
        req.META['HTTP_X_FORWARDED_FOR'] = ' 10.0.0.1 , 10.0.0.2'
        self.assertEqual(_client_ip(req), '10.0.0.1')
        req2 = self.factory.get('/')
        req2.META['REMOTE_ADDR'] = '127.0.0.1'
        self.assertEqual(_client_ip(req2), '127.0.0.1')

    def test_diff_instance_create_delete_none(self):
        self.assertEqual(diff_instance(None, None), {})
        cat = Category.objects.create(name='DiffCat', is_active=True)
        created = diff_instance(None, cat)
        self.assertIn('__created__', created)
        deleted = diff_instance(cat, None)
        self.assertIn('__deleted__', deleted)

    def test_log_audit_module_from_instance_and_repr_fallback(self):
        req = self.factory.post('/api/x/')
        req.user = self.user
        cat = Category.objects.create(name='LogCat', is_active=True)
        log_audit(req, AuditLog.ACTION_CREATE, cat)
        row = AuditLog.objects.get(object_id=str(cat.pk), action='create')
        self.assertEqual(row.module, 'products')

        broken = MagicMock()
        broken._meta.app_label = 'products'
        broken._meta.object_name = 'Broken'
        broken.pk = 99

        def boom():
            raise RuntimeError('no str')

        broken.__str__ = boom
        # str(broken) on MagicMock usually works; force via side_effect type
        class NoStr:
            class _meta:
                app_label = 'products'
                object_name = 'NoStr'

            pk = 42

            def __str__(self):
                raise RuntimeError('boom')

        log_audit(req, 'custom', NoStr(), module='')
        self.assertTrue(
            AuditLog.objects.filter(object_id='42', action='custom').exists()
        )
