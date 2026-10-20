"""Unit tests for audit helper writers."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from accounts.models import AuditLog
from products.models import Category, Product
from utils.audit_helpers import log_domain_event, log_model_change


class AuditHelpersTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('aud', password='x')
        self.request = RequestFactory().post('/')
        self.request.user = self.user

    def test_log_domain_event_persists_row(self):
        log_domain_event(
            self.request,
            'stock_adjust',
            module='inventory',
            changes={'quantity': 5},
            object_repr='ADJ-1',
        )
        row = AuditLog.objects.get(action='stock_adjust')
        self.assertEqual(row.module, 'inventory')
        self.assertEqual(row.changes['quantity'], 5)

    def test_log_model_change_records_diff(self):
        cat = Category.objects.create(name='C', is_active=True)
        before = Product.objects.create(
            name='P',
            sku='P-1',
            category=cat,
            price=Decimal('10'),
            is_active=True,
        )
        before_pk = before.pk
        before = Product.objects.get(pk=before_pk)
        before.price = Decimal('20')
        before.save()
        log_model_change(
            self.request,
            AuditLog.ACTION_UPDATE,
            before,
            module='products',
            before=Product.objects.get(pk=before_pk),
        )
        row = AuditLog.objects.get(module='products', action='update')
        self.assertIn('price', row.changes)

    def test_module_for_snapshot_and_safe_serializer(self):
        from unittest.mock import MagicMock

        from utils.audit_helpers import (
            _module_for,
            _snapshot,
            audited_perform_create,
            safe_serializer_data,
        )

        class View:
            audit_module = 'custom'
            request = self.request

        self.assertEqual(_module_for(View(), None), 'custom')

        class BareView:
            audit_module = None

        cat = Category.objects.create(name='AuditCat', is_active=True)
        self.assertEqual(_module_for(BareView(), cat), 'products')
        self.assertEqual(_module_for(BareView(), None), '')
        self.assertEqual(_snapshot(None), {})
        snap = _snapshot(cat)
        self.assertIn('name', snap)

        ser_ok = MagicMock()
        ser_ok.data = {'a': 1}
        self.assertEqual(safe_serializer_data(ser_ok), {'a': 1})
        ser_bad = MagicMock()
        type(ser_bad).data = property(lambda self: (_ for _ in ()).throw(RuntimeError('x')))
        self.assertEqual(safe_serializer_data(ser_bad), {})

        # audited_perform_create with serializer.data raising → empty __created__
        product_ser = MagicMock()
        product = Product.objects.create(
            name='AudP', sku='AUD-P1', category=cat, price=1, is_active=True,
        )
        product_ser.save.return_value = product
        type(product_ser).data = property(lambda self: (_ for _ in ()).throw(ValueError('bad')))
        out = audited_perform_create(View(), product_ser)
        self.assertEqual(out.pk, product.pk)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.ACTION_CREATE, module='custom').exists())
