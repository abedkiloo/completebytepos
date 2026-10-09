"""Query-budget checks for daily sales list (no per-order N+1)."""

from datetime import datetime
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from products.models import Category, Product
from sales.daily_sales import get_daily_sales_report
from sales.models import Sale, SaleItem
from utils.tests.api_test_base import SuperAdminAPITestCase


class DailySalesPerfTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cat = Category.objects.create(name='Daily Perf', is_active=True)
        product = Product.objects.create(
            name='Daily Perf SKU',
            sku='DAILY-PERF-1',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=500,
            track_stock=True,
            is_active=True,
        )
        tz = timezone.get_current_timezone()
        day = datetime(2026, 10, 9, 11, 0, 0)
        occurred = timezone.make_aware(day, tz)
        cls.date_str = '2026-10-09'
        cls.sale_ids = []
        for i in range(15):
            sale = Sale.objects.create(
                cashier=cls.admin,
                status='completed',
                sale_type='pos',
                subtotal=Decimal('100.00'),
                tax_amount=Decimal('0.00'),
                discount_amount=Decimal('0.00'),
                total=Decimal('100.00'),
                amount_paid=Decimal('100.00'),
                payment_method='cash',
                occurred_at=occurred,
            )
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=1 + (i % 3),
                unit_price=Decimal('100.00'),
                subtotal=Decimal(str(100 * (1 + (i % 3)))),
            )
            cls.sale_ids.append(sale.id)

    def test_daily_report_query_count_does_not_grow_with_order_count(self):
        with CaptureQueriesContext(connection) as ctx_full:
            report = get_daily_sales_report(
                date_str=self.date_str,
                page=1,
                page_size=25,
                user=self.admin,
            )
        self.assertEqual(report['summary']['orders_count'], 15)
        self.assertEqual(len(report['orders']), 15)
        for order in report['orders']:
            self.assertGreaterEqual(int(order['item_count']), 1)

        # Page of 5 vs 15 should stay flat (prefetch), not +2 queries per extra order.
        with CaptureQueriesContext(connection) as ctx_page:
            page = get_daily_sales_report(
                date_str=self.date_str,
                page=1,
                page_size=5,
                user=self.admin,
            )
        self.assertEqual(len(page['orders']), 5)
        # Without prefetch-aware serialize: ~2 queries/order → 30+ on a page of 15.
        self.assertLessEqual(
            len(ctx_full),
            30,
            msg=f'Daily sales used {len(ctx_full)} queries (likely N+1):\n'
            + '\n'.join(q['sql'][:160] for q in ctx_full.captured_queries[-12:]),
        )
        self.assertLessEqual(
            abs(len(ctx_full) - len(ctx_page)),
            4,
            msg=(
                f'Query count grew with page size '
                f'({len(ctx_page)} for 5 orders vs {len(ctx_full)} for 15).'
            ),
        )
