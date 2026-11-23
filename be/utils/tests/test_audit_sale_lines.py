"""Sale audit rows name the products so an item can be followed."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from accounts.models import AuditLog
from products.models import Category, Product
from sales.models import Customer, Sale, SaleItem
from utils.audit_events import log_call_write, log_sale_completed

PHONE = '0711666123'


class SaleLineAuditTests(TestCase):
    """A completed sale records each product and quantity, and not a phone."""

    def setUp(self):
        self.user = User.objects.create_user('line_cashier', password='x')
        self.request = RequestFactory().post('/api/sales/checkout/')
        self.request.user = self.user
        self.category = Category.objects.create(name='Audit lines', is_active=True)
        self.customer = Customer.objects.create(
            name='Line Buyer',
            phone=PHONE,
            customer_type='individual',
            is_active=True,
        )

    def _product(self, index):
        return Product.objects.create(
            name=f'Stand {index}',
            sku=f'AUD-LINE-{index}',
            category=self.category,
            price=Decimal('100'),
            is_active=True,
        )

    def _sale(self, count):
        sale = Sale.objects.create(
            sale_number=f'S-LINE-{count}',
            status='completed',
            sale_type='pos',
            cashier=self.user,
            customer=self.customer,
            subtotal=Decimal(count * 100),
            total=Decimal(count * 100),
            amount_paid=Decimal('50.00'),
            payment_method='cash',
        )
        for index in range(count):
            SaleItem.objects.create(
                sale=sale,
                product=self._product(index),
                quantity=index + 1,
                unit_price=Decimal('100.00'),
            )
        return sale

    def test_two_lines_keep_the_money_and_name_the_products(self):
        sale = self._sale(2)
        log_sale_completed(self.request, sale, source='checkout')
        row = AuditLog.objects.get(action='checkout', object_id=str(sale.id))
        self.assertEqual(row.changes['item_count'], 2)
        self.assertEqual(row.changes['lines'][0]['product'], 'Stand 0')
        self.assertEqual(row.changes['lines'][0]['quantity'], 1)
        self.assertEqual(row.changes['lines'][1]['quantity'], 2)
        self.assertEqual(row.changes['total'], '200')
        self.assertEqual(row.changes['amount_paid'], '50.00')
        self.assertNotIn(PHONE, str(row.changes))
        self.assertNotIn(PHONE, row.object_repr)
        sale.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal('50.00'))

    def test_forty_one_lines_keep_the_first_forty(self):
        sale = self._sale(41)
        log_sale_completed(self.request, sale, source='checkout')
        row = AuditLog.objects.get(action='checkout', object_id=str(sale.id))
        self.assertEqual(row.changes['item_count'], 41)
        self.assertEqual(len(row.changes['lines']), 40)
        self.assertEqual(row.changes['lines'][0]['product'], 'Stand 0')
        self.assertNotIn('Stand 40', str(row.changes['lines']))
        self.assertNotIn(PHONE, str(row.changes))

    def test_a_call_log_drops_a_phone_key(self):
        log_call_write(
            self.request,
            self.customer,
            kind='marked',
            detail={'outcome': 'called', 'phone': PHONE, 'request_summary': 'Hinges'},
        )
        row = AuditLog.objects.get(action='call_marked')
        self.assertEqual(row.changes['outcome'], 'called')
        self.assertEqual(row.changes['request_summary'], 'Hinges')
        self.assertNotIn('phone', row.changes)
        self.assertNotIn(PHONE, row.object_repr)
        self.assertNotIn(PHONE, str(row.changes))
