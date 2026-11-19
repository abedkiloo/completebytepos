"""New-price deliveries cannot be sold until a selling price is set."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from inventory.models import StockLayer
from inventory.services import StockMovementService
from inventory.stock_layers import plan_fifo_allocations, set_delivery_cost
from products.models import Category, Product
from sales.services import SaleService
from settings.settings_service import SettingsService
from settings.test_utils import disable_maker_checker


class PurchasePriceModeTests(TestCase):
    """Unit, sale, and corrected-cost checks for a delivery price choice."""

    def setUp(self):
        disable_maker_checker()
        self.user = User.objects.create_superuser(username='price_admin', password='x', email='p@example.com')
        cat = Category.objects.create(name='Price Cat', is_active=True)
        self.product = Product.objects.create(
            name='Hinges',
            sku='HINGE-PRICE-1',
            category=cat,
            price=Decimal('200.00'),
            mrp=Decimal('250.00'),
            cost=Decimal('80.00'),
            stock_quantity=0,
            track_stock=True,
            is_active=True,
        )
        self.inv = StockMovementService()
        self.sales = SaleService()

    def test_new_price_without_a_selling_price_cannot_be_sold(self):
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=4,
            user=self.user,
            price_mode='new',
        )
        layer = StockLayer.objects.get(product=self.product)
        self.assertTrue(layer.sale_price_pending)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('200.00'))
        with self.assertRaisesMessage(ValidationError, 'New sale price has not been set.'):
            plan_fifo_allocations(product_id=self.product.id, variant_id=None, quantity=1)

    def test_old_price_sells_at_the_current_price_and_keeps_shelf_stock(self):
        self.product.stock_quantity = 3
        self.product.save(update_fields=['stock_quantity'])
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=2,
            user=self.user,
            price_mode='old',
        )
        sale = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('1000.00')},
            [{'product_id': self.product.id, 'quantity': 4}],
            self.user,
        )
        prices = list(sale.items.order_by('id').values_list('unit_price', flat=True))
        self.assertEqual(prices, [Decimal('200.00'), Decimal('200.00')])

    def test_new_price_applies_only_to_the_new_pieces(self):
        self.product.stock_quantity = 2
        self.product.save(update_fields=['stock_quantity'])
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=2,
            unit_sell_price=Decimal('260.00'),
            unit_mrp=Decimal('300.00'),
            user=self.user,
            price_mode='new',
        )
        sale = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('1000.00')},
            [{'product_id': self.product.id, 'quantity': 3}],
            self.user,
        )
        prices = list(sale.items.order_by('id').values_list('unit_price', flat=True))
        self.assertEqual(prices[0], Decimal('200.00'))
        self.assertEqual(prices[-1], Decimal('260.00'))

    def test_admin_cost_changes_remaining_pieces_and_leaves_the_sale(self):
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=5,
            user=self.user,
            price_mode='old',
        )
        sale = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('400.00')},
            [{'product_id': self.product.id, 'quantity': 1}],
            self.user,
        )
        sold_cost = sale.items.first().unit_cost
        layer = StockLayer.objects.get(product=self.product, qty_remaining__gt=0)
        set_delivery_cost(layer_id=layer.id, unit_cost=Decimal('90.00'))
        sale.items.first().refresh_from_db()
        self.assertEqual(sale.items.first().unit_cost, sold_cost)
        nxt = plan_fifo_allocations(product_id=self.product.id, variant_id=None, quantity=1)
        self.assertEqual(nxt[0]['unit_cost'], Decimal('90.00'))

    def test_stress_two_hundred_unset_deliveries_all_block_the_sale(self):
        for _ in range(200):
            self.inv.purchase_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=1,
                user=self.user,
                price_mode='new',
            )
        self.assertEqual(
            StockLayer.objects.filter(product=self.product, sale_price_pending=True).count(),
            200,
        )
        with self.assertRaisesMessage(ValidationError, 'New sale price has not been set.'):
            self.sales.create_sale(
                {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('200.00')},
                [{'product_id': self.product.id, 'quantity': 1}],
                self.user,
            )


class PurchasePriceApiTests(TestCase):
    """API, module, and security checks for price and cost on a delivery."""

    def setUp(self):
        disable_maker_checker()
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='price_api_admin', password='x', email='pa@example.com',
        )
        self.staff = User.objects.create_user(username='price_staff', password='x')
        cat = Category.objects.create(name='Price API', is_active=True)
        self.product = Product.objects.create(
            name='Bolts',
            sku='BOLT-PRICE-1',
            category=cat,
            price=Decimal('50.00'),
            cost=Decimal('10.00'),
            stock_quantity=0,
            track_stock=True,
            is_active=True,
        )

    def test_purchase_defaults_to_new_price_and_search_shows_the_gap(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id,
            'quantity': 2,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        found = self.client.get('/api/products/search/', {'q': 'Bolts'})
        self.assertEqual(found.status_code, 200)
        row = next(item for item in found.data if item['id'] == self.product.id)
        self.assertTrue(row['new_sale_price_unset'])
        pending = self.client.get('/api/inventory/pending-prices/', {'product_id': self.product.id})
        self.assertTrue(pending.data[0]['sale_price_pending'])
        saved = self.client.post('/api/inventory/set-sale-price/', {
            'layer_id': pending.data[0]['layer_id'],
            'unit_sell_price': '75.00',
        }, format='json')
        self.assertEqual(saved.status_code, 200)
        self.assertFalse(saved.data['sale_price_pending'])

    def test_staff_cannot_set_cost_and_anonymous_is_rejected(self):
        self.client.force_authenticate(self.admin)
        self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id,
            'quantity': 1,
            'price_mode': 'old',
            'unit_cost': '999.00',
        }, format='json')
        layer = StockLayer.objects.get(product=self.product)
        self.assertEqual(layer.unit_cost, Decimal('10.00'))
        self.client.force_authenticate(self.staff)
        denied = self.client.post('/api/inventory/set-layer-cost/', {
            'layer_id': layer.id,
            'unit_cost': '40.00',
        }, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('0718', str(denied.data))
        anon = APIClient().post('/api/inventory/set-layer-cost/', {
            'layer_id': layer.id,
            'unit_cost': '40.00',
        }, format='json')
        self.assertEqual(anon.status_code, 401)

    def test_super_admin_sets_cost_and_purchases_off_blocks_the_price(self):
        self.client.force_authenticate(self.admin)
        self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id,
            'quantity': 1,
            'price_mode': 'old',
        }, format='json')
        layer = StockLayer.objects.get(product=self.product)
        saved = self.client.post('/api/inventory/set-layer-cost/', {
            'layer_id': layer.id,
            'unit_cost': '15.00',
        }, format='json')
        self.assertEqual(saved.status_code, 200)
        layer.refresh_from_db()
        self.assertEqual(layer.unit_cost, Decimal('15.00'))
        SettingsService.set('inventory', 'enable_stock_purchases', False)
        blocked = self.client.post('/api/inventory/set-sale-price/', {
            'layer_id': layer.id,
            'unit_sell_price': '60.00',
        }, format='json')
        self.assertEqual(blocked.status_code, 403)
        SettingsService.set('inventory', 'enable_stock_purchases', True)
