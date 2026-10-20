from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from accounts.models import AuditLog
from products.models import Category, Product
from sales.models import Sale
from utils.audit_events import (
    _money,
    log_approval_event,
    log_holding_cancelled,
    log_permission_denied,
    log_product_write,
    log_sale_completed,
    log_sale_date_corrected,
    log_sale_refunded,
    log_sale_rolled_back,
)


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

    def test_money_none_and_holding_cancel_permission_denied(self):
        self.assertEqual(_money(None), '')
        self.assertEqual(_money(Decimal('12.5')), '12.5')
        holding = Sale.objects.create(
            sale_number='HOLD-CANCEL',
            subtotal=Decimal('0'),
            total=Decimal('0'),
            amount_paid=Decimal('0'),
            payment_method='cash',
            status='holding',
            cashier=self.user,
        )
        log_holding_cancelled(self.request, holding)
        self.assertTrue(
            AuditLog.objects.filter(action='holding_cancel', module='sales').exists()
        )
        log_permission_denied(
            self.request, module='sales', action='delete', detail='nope',
        )
        row = AuditLog.objects.get(action=AuditLog.ACTION_PERMISSION_DENIED)
        self.assertEqual(row.changes['detail'], 'nope')

    def test_refund_rollback_date_approval_events(self):
        from datetime import datetime, timezone as dt_tz
        from types import SimpleNamespace

        sale = Sale.objects.create(
            sale_number='EVT-1',
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('50'),
            payment_method='cash',
            status='completed',
            cashier=self.user,
        )
        refund = SimpleNamespace(amount=Decimal('10'), reason='oops')
        log_sale_refunded(self.request, sale, refund)
        log_sale_rolled_back(self.request, sale, refund)
        prev = datetime(2024, 1, 1, tzinfo=dt_tz.utc)
        sale.occurred_at = datetime(2024, 2, 1, tzinfo=dt_tz.utc)
        log_sale_date_corrected(self.request, sale, previous=prev)
        log_approval_event(self.request, sale, module='approvals')
        self.assertTrue(AuditLog.objects.filter(action='approve', module='approvals').exists())
