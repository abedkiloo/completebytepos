"""Late/backfill sales SMS only when the operator opts in."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status

from messaging.customer_notify import notify_customer_sale_completed
from messaging.models import MessageOutbox
from products.models import Product
from sales.models import Customer, Sale
from sales.services import SaleService
from utils.tests.api_test_base import SuperAdminAPITestCase


class LateSaleSmsOptInTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        from settings.models import StoreSettings

        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.backfill_maker_checker_enabled = False
        store.save(
            update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled']
        )
        self.customer = Customer.objects.create(
            name='Jane Late',
            phone='0711111111',
            county='Nairobi',
            sub_county='Starehe',
            ward='Landimawe',
        )
        self.product = Product.objects.create(
            name='Cement',
            sku='CEM-SMS',
            price=Decimal('100.00'),
            cost=Decimal('60.00'),
            stock_quantity=50,
        )

    def test_direct_notify_skips_backfill_without_force(self):
        sale = Sale.objects.create(
            customer=self.customer,
            sale_number='SALE-BF-SMS-0',
            status='completed',
            sale_type='pos',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            change=Decimal('0'),
            payment_method='cash',
            entry_source='backfill',
        )
        self.assertIsNone(notify_customer_sale_completed(sale))
        self.assertIsNotNone(
            notify_customer_sale_completed(sale, force_late_entry=True)
        )
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=MessageOutbox.TEMPLATE_SALE_COMPLETED
            ).count(),
            1,
        )

    @patch('messaging.customer_notify.dispatch_outbox')
    def test_backfill_api_default_no_sms(self, _dispatch):
        occurred = timezone.now() - timedelta(days=1)
        response = self.client.post(
            '/api/sales/backfill/',
            {
                'occurred_at': occurred.isoformat(),
                'backfill_reason': 'Forgot to enter yesterday',
                'sale_type': 'pos',
                'customer_id': self.customer.id,
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
            },
            format='json',
        )
        if response.status_code == status.HTTP_202_ACCEPTED:
            self.skipTest('Maker-checker required for backfill in this env')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=MessageOutbox.TEMPLATE_SALE_COMPLETED
            ).count(),
            0,
        )

    @patch('messaging.customer_notify.dispatch_outbox')
    def test_backfill_api_opt_in_queues_sms(self, _dispatch):
        occurred = timezone.now() - timedelta(days=1)
        response = self.client.post(
            '/api/sales/backfill/',
            {
                'occurred_at': occurred.isoformat(),
                'backfill_reason': 'Customer asked for receipt SMS',
                'sale_type': 'pos',
                'customer_id': self.customer.id,
                'payment_method': 'cash',
                'amount_paid': '100.00',
                'notify_customer': True,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '100.00',
                    }
                ],
            },
            format='json',
        )
        if response.status_code == status.HTTP_202_ACCEPTED:
            self.skipTest('Maker-checker required for backfill in this env')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            MessageOutbox.objects.filter(
                template_key=MessageOutbox.TEMPLATE_SALE_COMPLETED
            ).count(),
            1,
        )

    def test_apply_sale_payment_defaults_off_for_late(self):
        sale = Sale.objects.create(
            customer=self.customer,
            sale_number='SALE-BF-SMS-2',
            status='completed',
            sale_type='pos',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'),
            discount_amount=Decimal('0'),
            total=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            change=Decimal('0'),
            payment_method='cash',
            entry_source='backfill',
        )
        payment = {
            'amount_paid_recorded': Decimal('100.00'),
            'change': Decimal('0'),
            'wallet_amount_used': Decimal('0'),
            'wallet_credit_added': Decimal('0'),
            'unpaid_amount': Decimal('0'),
        }
        with patch(
            'messaging.customer_notify.notify_customer_sale_completed'
        ) as notify:
            SaleService()._apply_sale_payment(
                self.customer, sale, self.admin, payment
            )
            notify.assert_not_called()
            SaleService()._apply_sale_payment(
                self.customer,
                sale,
                self.admin,
                payment,
                notify_customer=True,
            )
            notify.assert_called_once()
            self.assertTrue(notify.call_args.kwargs.get('force_late_entry'))
