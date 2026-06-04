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
