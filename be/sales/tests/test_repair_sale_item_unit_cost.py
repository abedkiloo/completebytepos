"""One-shot SaleItem.unit_cost alignment from movements / catalog."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from inventory.models import StockMovement
from products.models import Category, Product
from sales.models import Sale, SaleItem
from sales.repair_sale_item_unit_cost import (
    apply_unit_cost_repairs,
    plan_unit_cost_repairs,
    repair_unit_costs,
)


class RepairSaleItemUnitCostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cost_fix', password='x')
        self.category = Category.objects.create(name='Hardware Cost Align')
        self.product = Product.objects.create(
            name='NO 5 Zipper',
            sku='ZIP-5',
            category=self.category,
            price=Decimal('1550.00'),
            cost=Decimal('3600.00'),
            stock_quantity=500,
            track_stock=True,
            is_active=True,
        )
        self.sale = Sale.objects.create(
            sale_number='SALE-COST-ALIGN-1',
            status='completed',
            sale_type='pos',
            subtotal=Decimal('170500.00'),
            total=Decimal('170500.00'),
            amount_paid=Decimal('0'),
            payment_method='credit',
            cashier=self.user,
            occurred_at=timezone.now(),
        )
        self.item = SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            quantity=110,
            unit_price=Decimal('1550.00'),
            subtotal=Decimal('170500.00'),
            unit_cost=Decimal('0'),  # historical bad stamp
        )
        StockMovement.objects.create(
            product=self.product,
            movement_type='sale',
            quantity=-110,
            unit_cost=Decimal('3600.00'),
            total_cost=Decimal('396000.00'),
            reference=self.sale.sale_number,
            user=self.user,
        )

    def test_plan_uses_stock_movement_when_stamp_is_zero(self):
        repairs = plan_unit_cost_repairs([self.item])
        self.assertEqual(len(repairs), 1)
        self.assertEqual(repairs[0].source, 'stock_movement')
        self.assertEqual(repairs[0].new_unit_cost, Decimal('3600.0000'))

    def test_apply_stamps_unit_cost_and_is_idempotent(self):
        repairs, applied = repair_unit_costs(
            sale_numbers=[self.sale.sale_number],
            apply=True,
        )
        self.assertEqual(len(repairs), 1)
        self.assertEqual(applied, 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_cost, Decimal('3600.0000'))

        again, applied_again = repair_unit_costs(
            sale_numbers=[self.sale.sale_number],
            apply=True,
        )
        self.assertEqual(again, [])
        self.assertEqual(applied_again, 0)

    def test_catalog_fallback_when_no_movement(self):
        StockMovement.objects.filter(reference=self.sale.sale_number).delete()
        repairs = plan_unit_cost_repairs([self.item])
        self.assertEqual(len(repairs), 1)
        self.assertEqual(repairs[0].source, 'catalog')
        self.assertEqual(repairs[0].new_unit_cost, Decimal('3600.0000'))

    def test_dry_run_does_not_write(self):
        repairs, applied = repair_unit_costs(
            sale_numbers=[self.sale.sale_number],
            apply=False,
        )
        self.assertEqual(len(repairs), 1)
        self.assertEqual(applied, 0)
        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_cost, Decimal('0'))

    def test_apply_helper_skips_already_positive(self):
        self.item.unit_cost = Decimal('10.00')
        self.item.save(update_fields=['unit_cost'])
        from sales.repair_sale_item_unit_cost import UnitCostRepairRow

        fake = UnitCostRepairRow(
            sale_item_id=self.item.id,
            sale_number=self.sale.sale_number,
            product_name='x',
            quantity=Decimal('1'),
            old_unit_cost=Decimal('0'),
            new_unit_cost=Decimal('99'),
            source='catalog',
        )
        self.assertEqual(apply_unit_cost_repairs([fake]), 0)
