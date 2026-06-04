from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from accounts.models import AuditLog
from products.models import Category, Product
from sales.models import Sale
from utils.audit_events import log_product_write, log_sale_completed


class AuditEventsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user('cashier', password='x')
        self.request = self.factory.post('/api/sales/')
        self.request.user = self.user

    def test_log_sale_completed(self):
        sale = Sale.objects.create(
            sale_number='HOLD-1',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            amount_paid=Decimal('100'),
            payment_method='cash',
            status='completed',
            cashier=self.user,
        )
        log_sale_completed(self.request, sale, source='checkout')
        row = AuditLog.objects.get(action='checkout', module='sales')
        self.assertEqual(row.changes['total'], '100')

    def test_log_product_write_update(self):
        cat = Category.objects.create(name='C', is_active=True)
        product = Product.objects.create(
            name='P',
            sku='P-1',
            category=cat,
            price=Decimal('10'),
            is_active=True,
        )
        before = Product.objects.get(pk=product.pk)
        product.price = Decimal('15')
        product.save()
        log_product_write(
            self.request,
            product,
            before=before,
            action=AuditLog.ACTION_UPDATE,
        )
        self.assertEqual(
            AuditLog.objects.filter(action='update', module='products').count(),
            1,
        )
