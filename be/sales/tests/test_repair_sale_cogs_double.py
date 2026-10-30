"""Surplus/shortfall sale drains after correction must be auditable and repairable."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from inventory.models import StockMovement
from products.models import Category, Product
from reports.trading_profit import _cogs_for_sales
from sales.models import Sale, SaleItem
from sales.repair_sale_cogs_double import audit_sale_cogs, repair_sale_cogs_double


class RepairSaleCogsDoubleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cogs_fix', password='x')
        cat = Category.objects.create(name='Cogs Fix', is_active=True)
        self.product = Product.objects.create(
            name='Fix Item',
            sku='COGS-FIX-1',
            category=cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )

    def _sale(self, number, qty, *, unit_cost=None):
        sale = Sale.objects.create(
            sale_number=number,
            status='completed',
            cashier=self.user,
            subtotal=Decimal(str(qty * 100)),
            total=Decimal(str(qty * 100)),
            amount_paid=Decimal(str(qty * 100)),
            payment_method='cash',
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=qty,
            unit_price=Decimal('100'),
            unit_cost=unit_cost,
            subtotal=Decimal(str(qty * 100)),
        )
        return sale

    def _drain(self, sale, qty, *, unit_cost=Decimal('40'), notes=''):
        StockMovement.objects.create(
            product=self.product,
            movement_type='sale',
            quantity=qty,
            unit_cost=unit_cost,
            total_cost=unit_cost * qty,
            reference=sale.sale_number,
            user=self.user,
            notes=notes,
        )

    def test_qty_reduced_3_to_1_surplus_cleared(self):
        """Entered 3, corrected to 1 — leftover drains must not keep COGS at 3×."""
        sale = self._sale('SALE-COGS-DOWN', qty=1, unit_cost=None)
        self._drain(sale, 1)  # current
        self._drain(sale, 2, notes='stale pre-correction (was qty 3)')

        before = _cogs_for_sales(Sale.objects.filter(pk=sale.pk))
        self.assertEqual(before, Decimal('120'))  # 3 units × 40 via movements

        audit = audit_sale_cogs(sale)
        self.assertEqual(audit.item_qty, 1)
        self.assertEqual(audit.live_sale_mov_qty, 3)
        self.assertTrue(audit.surplus_movements)
        self.assertFalse(audit.needs_recomplete)

        result = repair_sale_cogs_double(
            sale_numbers=[sale.sale_number],
            apply=True,
            restamp_unit_cost=True,
        )
        self.assertGreaterEqual(result['voided'], 1)
        after = _cogs_for_sales(Sale.objects.filter(pk=sale.pk))
        self.assertEqual(after, Decimal('40'))

    def test_qty_increased_2_to_5_flags_shortfall(self):
        """Entered 2, corrected to 5 — movements still at 2 need re-approve."""
        sale = self._sale('SALE-COGS-UP', qty=5, unit_cost=Decimal('40'))
        self._drain(sale, 2, notes='stale pre-correction (was qty 2)')

        audit = audit_sale_cogs(sale)
        self.assertEqual(audit.shortfall_qty, 3)
        self.assertTrue(audit.needs_recomplete)
        self.assertTrue(any('shortfall' in i for i in audit.issues))

