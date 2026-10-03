"""Every completed sale reduces stock — regardless of the stock validation setting."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from inventory.models import StockMovement
from products.models import Category, Color, Product, ProductVariant, Size
from sales.services import SaleService
from settings.models import ModuleSetting


def _set_stock_validation(enabled: bool):
    cache.clear()
    ModuleSetting.objects.update_or_create(
        module='sales',
        key='validate_stock_before_sale',
        defaults={
            'label': 'Validate stock before sale',
            'description': '',
            'default_value': True,
            'value': enabled,
        },
    )
    cache.clear()


class SaleStockDeductionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('stock_deduct_user', password='x')
        cls.category = Category.objects.create(name='Deduct Cat', is_active=True)
        cls.size_s = Size.objects.create(name='DS', code='DS')
        cls.size_m = Size.objects.create(name='DM', code='DM')
        cls.color = Color.objects.create(name='DRed')

    def setUp(self):
        _set_stock_validation(True)
        self.addCleanup(cache.clear)
        self.product = Product.objects.create(
            name='Sized Shirt',
            sku='DED-1',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('40.00'),
            stock_quantity=0,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        self.variant_s = ProductVariant.objects.create(
            product=self.product, size=self.size_s, color=self.color,
            sku='DED-1-S', stock_quantity=2, is_active=True,
        )
        self.variant_m = ProductVariant.objects.create(
            product=self.product, size=self.size_m, color=self.color,
            sku='DED-1-M', stock_quantity=3, is_active=True,
        )

    def _sell(self, quantity, variant=None):
        SaleService()._create_sale_stock_movements(
            branch=None,
            user=self.user,
            reference='DED-SALE',
            notes='test',
            product=self.product,
            variant=variant,
            quantity=quantity,
            unit_cost=Decimal('40.00'),
        )
        self.variant_s.refresh_from_db()
        self.variant_m.refresh_from_db()
        self.product.refresh_from_db()

    def test_sale_without_size_draws_from_sizes_not_parent(self):
        self._sell(3)
        self.assertEqual(self.variant_s.stock_quantity, 0)
        self.assertEqual(self.variant_m.stock_quantity, 2)
        self.assertEqual(self.product.stock_quantity, 2)
        self.assertFalse(
            StockMovement.objects.filter(reference='DED-SALE', variant__isnull=True).exists()
        )

    def test_oversell_without_size_uses_up_all_sizes(self):
        _set_stock_validation(False)
        self._sell(7)
        self.assertEqual(self.variant_s.stock_quantity, 0)
        self.assertEqual(self.variant_m.stock_quantity, 0)
        self.assertEqual(self.product.stock_quantity, 0)

    def test_oversell_with_validation_on_is_refused(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self._sell(7)

    def test_simple_product_reduces_when_validation_off(self):
        _set_stock_validation(False)
        simple = Product.objects.create(
            name='Plain Mug', sku='DED-2', category=self.category,
            price=Decimal('50.00'), cost=Decimal('20.00'),
            stock_quantity=10, track_stock=True, is_active=True,
        )
        SaleService()._create_sale_stock_movements(
            branch=None, user=self.user, reference='DED-MUG', notes='test',
            product=simple, variant=None, quantity=4, unit_cost=Decimal('20.00'),
        )
        simple.refresh_from_db()
        self.assertEqual(simple.stock_quantity, 6)

    def test_audit_lists_sales_that_did_not_reduce_stock(self):
        from io import StringIO

        from django.core.management import call_command
        from sales.models import Sale, SaleItem

        mug = Product.objects.create(
            name='Audit Mug', sku='DED-3', category=self.category,
            price=Decimal('50.00'), cost=Decimal('20.00'),
            stock_quantity=10, track_stock=True, is_active=True,
        )
        for number, reduce in (('AUD-OK', True), ('AUD-MISSING', False)):
            sale = Sale.objects.create(
                sale_number=number, status='completed', subtotal=Decimal('100'),
                total=Decimal('100'), amount_paid=Decimal('100'), payment_method='cash',
                cashier=self.user,
            )
            SaleItem.objects.create(
                sale=sale, product=mug, quantity=2,
                unit_price=Decimal('50'), subtotal=Decimal('100'),
            )
            if reduce:
                SaleService()._create_sale_stock_movements(
                    branch=None, user=self.user, reference=number, notes='t',
                    product=mug, variant=None, quantity=2, unit_cost=Decimal('20'),
                )
        out = StringIO()
        call_command('audit_sale_stock', stdout=out)
        text = out.getvalue()
        self.assertIn('AUD-MISSING  STOCK NOT REDUCED', text)
        self.assertNotIn('AUD-OK  STOCK NOT REDUCED', text)
        self.assertIn('Audit Mug: sold 2, stock reduced by 0', text)
        self.assertIn('Audit Mug: 2', text)

    def test_sale_with_size_reduces_that_size(self):
        self._sell(2, variant=self.variant_m)
        self.assertEqual(self.variant_m.stock_quantity, 1)
        self.assertEqual(self.variant_s.stock_quantity, 2)
        self.assertEqual(self.product.stock_quantity, 3)
