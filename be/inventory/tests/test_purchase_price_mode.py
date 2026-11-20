"""New-price deliveries cannot be sold until a selling price is set."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from inventory.models import StockLayer
from inventory.services import StockMovementService
from inventory.stock_layers import plan_fifo_allocations, set_delivery_cost, set_delivery_sale_price
from products.models import Category, Product, ProductVariant, Size
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

    def test_a_higher_new_price_stops_at_the_pieces_already_priced(self):
        self.product.stock_quantity = 10
        self.product.save(update_fields=['stock_quantity'])
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=2,
            unit_sell_price=Decimal('260.00'),
            user=self.user,
            price_mode='new',
        )
        with self.assertRaisesMessage(ValidationError, 'You can only sell 10.'):
            self.sales.create_sale(
                {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('2200.00')},
                [{'product_id': self.product.id, 'quantity': 11}],
                self.user,
            )
        sale = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('2000.00')},
            [{'product_id': self.product.id, 'quantity': 10}],
            self.user,
        )
        self.assertEqual(sale.items.first().unit_price, Decimal('200.00'))

    def test_a_lower_new_price_sells_the_extra_piece_at_the_old_price(self):
        self.product.price = Decimal('260.00')
        self.product.stock_quantity = 10
        self.product.save(update_fields=['price', 'stock_quantity'])
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=1,
            unit_sell_price=Decimal('200.00'),
            user=self.user,
            price_mode='new',
        )
        sale = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('3000.00')},
            [{'product_id': self.product.id, 'quantity': 11}],
            self.user,
        )
        prices = list(sale.items.values_list('unit_price', flat=True))
        self.assertTrue(prices)
        self.assertTrue(all(price == Decimal('260.00') for price in prices))
        charged = sum((item.subtotal for item in sale.items.all()), Decimal('0'))
        self.assertEqual(charged, Decimal('2860.00'))

    def test_existing_stock_price_math_keeps_the_new_price_for_later(self):
        self.product.price = Decimal('200.00')
        self.product.cost = Decimal('20.00')
        self.product.stock_quantity = 10
        self.product.save(update_fields=['price', 'cost', 'stock_quantity'])
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=2,
            unit_sell_price=Decimal('150.00'),
            user=self.user,
            price_mode='new',
        )
        mixed = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('2200.00')},
            [{'product_id': self.product.id, 'quantity': 11}],
            self.user,
        )
        charged = sum((item.subtotal for item in mixed.items.all()), Decimal('0'))
        self.assertEqual(charged, Decimal('2200.00'))
        extra = mixed.items.order_by('id').last()
        self.assertEqual(extra.unit_price, Decimal('200.00'))
        self.assertEqual(extra.unit_cost, Decimal('20.00'))
        newest = StockLayer.objects.filter(product=self.product).order_by('-id').first()
        self.assertEqual(newest.unit_sell_price, Decimal('150.00'))
        later = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('150.00')},
            [{'product_id': self.product.id, 'quantity': 1}],
            self.user,
        )
        self.assertEqual(later.items.first().unit_price, Decimal('150.00'))
        self.assertEqual(later.items.first().subtotal, Decimal('150.00'))

    def test_priced_pieces_sell_before_the_new_price_is_set(self):
        self.product.stock_quantity = 10
        self.product.save(update_fields=['stock_quantity'])
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=5,
            user=self.user,
            price_mode='new',
        )
        with self.assertRaises(ValidationError) as caught:
            self.sales.create_sale(
                {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('2200.00')},
                [{'product_id': self.product.id, 'quantity': 11}],
                self.user,
            )
        self.assertIn('You can sell 10. New sale price has not been set.', str(caught.exception))
        self.assertNotIn('0718', str(caught.exception))
        sale = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('2000.00')},
            [{'product_id': self.product.id, 'quantity': 10}],
            self.user,
        )
        self.assertEqual(sale.items.first().unit_price, Decimal('200.00'))

    def test_stress_two_hundred_unpriced_pieces_still_leave_the_old_ten_sellable(self):
        self.product.stock_quantity = 10
        self.product.save(update_fields=['stock_quantity'])
        for _ in range(200):
            self.inv.purchase_stock(
                product_id=self.product.id,
                variant_id=None,
                quantity=1,
                user=self.user,
                price_mode='new',
            )
        with self.assertRaisesMessage(ValidationError, 'You can sell 10.'):
            plan_fifo_allocations(product_id=self.product.id, variant_id=None, quantity=11)
        plan = plan_fifo_allocations(product_id=self.product.id, variant_id=None, quantity=10)
        self.assertEqual(sum(row['quantity'] for row in plan), 10)
        self.assertEqual(plan[0]['unit_sell_price'], Decimal('200.00'))

    def test_layers_off_does_not_block_a_higher_new_price(self):
        self.product.stock_quantity = 10
        self.product.save(update_fields=['stock_quantity'])
        SettingsService.set('inventory', 'enable_stock_layers', False)
        try:
            plan = plan_fifo_allocations(product_id=self.product.id, variant_id=None, quantity=11)
        finally:
            SettingsService.set('inventory', 'enable_stock_layers', True)
        self.assertEqual(plan[0]['unit_sell_price'], Decimal('200.00'))

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

    def test_a_huge_delivery_quantity_is_refused(self):
        self.client.force_authenticate(self.admin)
        huge = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id,
            'quantity': 1000001,
            'price_mode': 'old',
        }, format='json')
        self.assertEqual(huge.status_code, 400, huge.data)
        self.assertNotIn('0718', str(huge.data))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)

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


class ExistingStockTests(TestCase):
    """A delivery adds on top. A count correction leaves the price alone."""

    def setUp(self):
        disable_maker_checker()
        self.user = User.objects.create_superuser(username='stock_admin', password='x', email='s@example.com')
        self.staff = User.objects.create_user(username='stock_staff', password='x')
        cat = Category.objects.create(name='Shelf Cat', is_active=True)
        self.product = Product.objects.create(
            name='Nails',
            sku='NAIL-SHELF-1',
            category=cat,
            price=Decimal('50.00'),
            mrp=Decimal('70.00'),
            cost=Decimal('20.00'),
            stock_quantity=0,
            track_stock=True,
            is_active=True,
        )
        self.inv = StockMovementService()
        self.client = APIClient()

    def test_a_delivery_adds_on_top_of_stock_already_there(self):
        self.inv.purchase_stock(
            product_id=self.product.id, variant_id=None, quantity=6,
            user=self.user, price_mode='old',
        )
        self.inv.purchase_stock(
            product_id=self.product.id, variant_id=None, quantity=4,
            user=self.user, price_mode='new', unit_sell_price=Decimal('80.00'),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.product.price, Decimal('50.00'))
        self.assertEqual(self.product.mrp, Decimal('70.00'))
        newest = StockLayer.objects.filter(product=self.product).order_by('-id').first()
        self.assertEqual(newest.unit_sell_price, Decimal('80.00'))

    def test_correcting_the_count_does_not_change_price_or_mrp(self):
        self.inv.purchase_stock(
            product_id=self.product.id, variant_id=None, quantity=6,
            user=self.user, price_mode='old',
        )
        self.inv.set_on_hand_count(product_id=self.product.id, quantity=9, user=self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertEqual(self.product.price, Decimal('50.00'))
        self.assertEqual(self.product.mrp, Decimal('70.00'))
        self.inv.set_on_hand_count(product_id=self.product.id, quantity=4, user=self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 4)
        self.assertEqual(self.product.mrp, Decimal('70.00'))

    def test_only_a_manager_or_super_admin_can_correct_the_count(self):
        from inventory.access import may_correct_on_hand
        self.assertFalse(may_correct_on_hand(self.staff))
        self.assertTrue(may_correct_on_hand(self.user))
        self.inv.purchase_stock(
            product_id=self.product.id, variant_id=None, quantity=6,
            user=self.user, price_mode='old',
        )
        self.client.force_authenticate(self.staff)
        denied = self.client.post('/api/inventory/set-on-hand/', {
            'product_id': self.product.id, 'quantity': 3,
        }, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('0718', str(denied.data))
        anon = APIClient().post('/api/inventory/set-on-hand/', {
            'product_id': self.product.id, 'quantity': 3,
        }, format='json')
        self.assertEqual(anon.status_code, 401)
        self.client.force_authenticate(self.user)
        saved = self.client.post('/api/inventory/set-on-hand/', {
            'product_id': self.product.id, 'quantity': 3,
        }, format='json')
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.data['stock_quantity'], 3)
        self.assertTrue(saved.data['price_unchanged'])
        self.assertTrue(saved.data['mrp_unchanged'])


class UpdateSellingPriceLaterTests(TestCase):
    """A selling price already saved can be changed for pieces still in stock."""

    def setUp(self):
        disable_maker_checker()
        self.user = User.objects.create_superuser(username='later_admin', password='x', email='l@example.com')
        self.staff = User.objects.create_user(username='later_staff', password='x')
        cat = Category.objects.create(name='Later Cat', is_active=True)
        self.product = Product.objects.create(
            name='Screws',
            sku='SCREW-LATER-1',
            category=cat,
            price=Decimal('50.00'),
            mrp=Decimal('70.00'),
            cost=Decimal('20.00'),
            stock_quantity=0,
            track_stock=True,
            is_active=True,
        )
        self.inv = StockMovementService()
        self.sales = SaleService()
        self.client = APIClient()

    def _deliver(self, quantity=4):
        self.inv.purchase_stock(
            product_id=self.product.id,
            variant_id=None,
            quantity=quantity,
            user=self.user,
            price_mode='old',
        )
        return StockLayer.objects.get(product=self.product, qty_remaining__gt=0)

    def test_a_blank_or_huge_price_is_refused(self):
        layer = self._deliver()
        with self.assertRaisesMessage(ValidationError, 'Enter a selling price greater than 0.'):
            set_delivery_sale_price(layer_id=layer.id, unit_sell_price='0')
        with self.assertRaisesMessage(ValidationError, 'Enter a selling price greater than 0.'):
            set_delivery_sale_price(layer_id=layer.id, unit_sell_price='100000000')
        layer.refresh_from_db()
        self.assertEqual(layer.unit_sell_price, Decimal('50.00'))

    def test_a_later_price_applies_only_to_pieces_still_in_stock(self):
        layer = self._deliver()
        sale = self.sales.create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('50.00')},
            [{'product_id': self.product.id, 'quantity': 1}],
            self.user,
        )
        sold = sale.items.first().unit_price
        set_delivery_sale_price(layer_id=layer.id, unit_sell_price=Decimal('90.00'))
        sale.items.first().refresh_from_db()
        self.assertEqual(sale.items.first().unit_price, sold)
        nxt = plan_fifo_allocations(product_id=self.product.id, variant_id=None, quantity=1)
        self.assertEqual(nxt[0]['unit_sell_price'], Decimal('90.00'))

    def test_the_api_updates_a_price_that_was_already_set(self):
        layer = self._deliver()
        self.client.force_authenticate(self.user)
        saved = self.client.post('/api/inventory/set-sale-price/', {
            'layer_id': layer.id,
            'unit_sell_price': '90.00',
        }, format='json')
        self.assertEqual(saved.status_code, 200)
        layer.refresh_from_db()
        self.assertEqual(layer.unit_sell_price, Decimal('90.00'))
        self.assertFalse(layer.sale_price_pending)

    def test_purchases_off_blocks_a_later_price_and_on_allows_it(self):
        layer = self._deliver()
        self.client.force_authenticate(self.user)
        SettingsService.set('inventory', 'enable_stock_purchases', False)
        blocked = self.client.post('/api/inventory/set-sale-price/', {
            'layer_id': layer.id, 'unit_sell_price': '90.00',
        }, format='json')
        self.assertEqual(blocked.status_code, 403)
        SettingsService.set('inventory', 'enable_stock_purchases', True)
        allowed = self.client.post('/api/inventory/set-sale-price/', {
            'layer_id': layer.id, 'unit_sell_price': '90.00',
        }, format='json')
        self.assertEqual(allowed.status_code, 200)

    def test_stress_two_hundred_price_updates_keep_the_last_price(self):
        layer = self._deliver()
        for step in range(1, 201):
            set_delivery_sale_price(layer_id=layer.id, unit_sell_price=Decimal(step))
        layer.refresh_from_db()
        self.assertEqual(layer.unit_sell_price, Decimal('200'))

    def test_staff_and_anonymous_cannot_update_the_selling_price(self):
        layer = self._deliver()
        self.client.force_authenticate(self.staff)
        denied = self.client.post('/api/inventory/set-sale-price/', {
            'layer_id': layer.id, 'unit_sell_price': '90.00',
        }, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('0718', str(denied.data))
        anon = APIClient().post('/api/inventory/set-sale-price/', {
            'layer_id': layer.id, 'unit_sell_price': '90.00',
        }, format='json')
        self.assertEqual(anon.status_code, 401)
        layer.refresh_from_db()
        self.assertEqual(layer.unit_sell_price, Decimal('50.00'))


class VariantStockingTests(TestCase):
    """A delivery and a count correction apply to one size and colour."""

    def setUp(self):
        disable_maker_checker()
        self.user = User.objects.create_superuser(username='var_admin', password='x', email='v@example.com')
        self.staff = User.objects.create_user(username='var_staff', password='x')
        cat = Category.objects.create(name='Variant Cat', is_active=True)
        self.product = Product.objects.create(
            name='Cloth',
            sku='CLOTH-VAR-1',
            category=cat,
            price=Decimal('100.00'),
            cost=Decimal('20.00'),
            stock_quantity=0,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        medium = Size.objects.create(name='Medium', code='M', is_active=True)
        large = Size.objects.create(name='Large', code='L', is_active=True)
        self.medium = ProductVariant.objects.create(
            product=self.product, size=medium, sku='CLOTH-M',
            price=Decimal('200.00'), cost=Decimal('20.00'),
            stock_quantity=10, is_active=True,
        )
        self.large = ProductVariant.objects.create(
            product=self.product, size=large, sku='CLOTH-L',
            price=Decimal('150.00'), cost=Decimal('20.00'),
            stock_quantity=4, is_active=True,
        )
        self.inv = StockMovementService()
        self.client = APIClient()

    def test_a_delivery_without_a_size_is_refused(self):
        with self.assertRaisesMessage(ValidationError, 'Choose a size and colour.'):
            self.inv.purchase_stock(
                product_id=self.product.id, variant_id=None, quantity=1,
                user=self.user, price_mode='old',
            )

    def test_a_delivery_adds_only_to_that_size_at_its_price(self):
        self.inv.purchase_stock(
            product_id=self.product.id, variant_id=self.medium.id, quantity=2,
            user=self.user, price_mode='old',
        )
        self.medium.refresh_from_db()
        self.large.refresh_from_db()
        self.assertEqual(self.medium.stock_quantity, 12)
        self.assertEqual(self.large.stock_quantity, 4)
        layer = StockLayer.objects.filter(variant=self.medium).order_by('-id').first()
        self.assertEqual(layer.unit_sell_price, Decimal('200.00'))
        self.assertFalse(StockLayer.objects.filter(variant=self.large).exists())

    def test_a_higher_price_on_one_size_does_not_stop_the_other(self):
        self.inv.purchase_stock(
            product_id=self.product.id, variant_id=self.medium.id, quantity=1,
            user=self.user, price_mode='new', unit_sell_price=Decimal('260.00'),
        )
        with self.assertRaisesMessage(ValidationError, 'You can only sell 10.'):
            plan_fifo_allocations(product_id=self.product.id, variant_id=self.medium.id, quantity=11)
        other = plan_fifo_allocations(product_id=self.product.id, variant_id=self.large.id, quantity=4)
        self.assertEqual(other[0]['unit_sell_price'], Decimal('150.00'))

    def test_correcting_one_size_leaves_the_other_price_and_count(self):
        self.inv.set_on_hand_count(
            product_id=self.product.id, variant_id=self.medium.id, quantity=7, user=self.user,
        )
        self.medium.refresh_from_db()
        self.large.refresh_from_db()
        self.assertEqual(self.medium.stock_quantity, 7)
        self.assertEqual(self.medium.price, Decimal('200.00'))
        self.assertEqual(self.large.stock_quantity, 4)
        self.assertEqual(self.large.price, Decimal('150.00'))

    def test_api_requires_the_size_and_hides_other_sizes(self):
        self.client.force_authenticate(self.user)
        missing = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'quantity': 1, 'price_mode': 'old',
        }, format='json')
        self.assertEqual(missing.status_code, 400)
        self.assertIn('Choose a size', str(missing.data))
        self.assertNotIn('0718', str(missing.data))
        saved = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': self.medium.id,
            'quantity': 1, 'price_mode': 'old',
        }, format='json')
        self.assertEqual(saved.status_code, 201, saved.data)
        rows = self.client.get('/api/inventory/pending-prices/', {
            'product_id': self.product.id, 'variant_id': self.large.id,
        })
        self.assertEqual(rows.status_code, 200)
        self.assertEqual(rows.data, [])
        self.client.force_authenticate(self.staff)
        denied = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': self.medium.id, 'quantity': 1,
        }, format='json')
        self.assertEqual(denied.status_code, 403)
        anon = APIClient().post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': self.medium.id, 'quantity': 1,
        }, format='json')
        self.assertEqual(anon.status_code, 401)

    def test_purchases_off_blocks_a_size_and_on_allows_it(self):
        self.client.force_authenticate(self.user)
        SettingsService.set('inventory', 'enable_stock_purchases', False)
        blocked = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': self.medium.id,
            'quantity': 1, 'price_mode': 'old',
        }, format='json')
        self.assertEqual(blocked.status_code, 403)
        SettingsService.set('inventory', 'enable_stock_purchases', True)
        allowed = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': self.medium.id,
            'quantity': 1, 'price_mode': 'old',
        }, format='json')
        self.assertEqual(allowed.status_code, 201, allowed.data)

    def test_stress_two_hundred_unpriced_pieces_stay_on_one_size(self):
        for _ in range(200):
            self.inv.purchase_stock(
                product_id=self.product.id, variant_id=self.medium.id, quantity=1,
                user=self.user, price_mode='new',
            )
        with self.assertRaisesMessage(ValidationError, 'You can sell 10.'):
            plan_fifo_allocations(product_id=self.product.id, variant_id=self.medium.id, quantity=11)
        self.large.refresh_from_db()
        self.assertEqual(self.large.stock_quantity, 4)

    def test_one_size_sale_total_uses_that_sizes_old_price(self):
        self.inv.purchase_stock(
            product_id=self.product.id, variant_id=self.medium.id, quantity=1,
            user=self.user, price_mode='new', unit_sell_price=Decimal('180.00'),
        )
        sale = SaleService().create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('2200.00')},
            [{'product_id': self.product.id, 'variant_id': self.medium.id, 'quantity': 11}],
            self.user,
        )
        charged = sum((item.subtotal for item in sale.items.all()), Decimal('0'))
        self.assertEqual(charged, Decimal('2200.00'))
        newest = StockLayer.objects.filter(variant=self.medium).order_by('-id').first()
        self.assertEqual(newest.unit_sell_price, Decimal('180.00'))
        self.assertEqual(newest.unit_cost, Decimal('20.00'))
        self.large.refresh_from_db()
        self.assertEqual(self.large.stock_quantity, 4)
        self.assertEqual(self.large.price, Decimal('150.00'))

    def test_only_a_super_admin_sets_cost_on_a_size(self):
        from products.serializers import ProductVariantSerializer

        self.inv.adjust_stock(
            product_id=self.product.id,
            variant_id=self.medium.id,
            quantity=1,
            unit_cost=Decimal('999.00'),
            user=self.staff,
        )
        added = StockLayer.objects.filter(variant=self.medium).order_by('-id').first()
        self.assertEqual(added.unit_cost, Decimal('20.00'))
        self.assertEqual(added.unit_sell_price, Decimal('200.00'))
        request = type('Req', (), {'user': self.staff})()
        edited = ProductVariantSerializer(
            self.medium,
            data={'cost': '999.00', 'price': '210.00'},
            partial=True,
            context={'request': request},
        )
        self.assertTrue(edited.is_valid(), edited.errors)
        self.assertNotIn('cost', edited.validated_data)
        self.assertEqual(edited.validated_data['price'], Decimal('210.00'))
        self.client.force_authenticate(self.staff)
        denied = self.client.post('/api/inventory/set-layer-cost/', {
            'layer_id': added.id, 'unit_cost': '30.00',
        }, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('0718', str(denied.data))
        self.client.force_authenticate(self.user)
        saved = self.client.post('/api/inventory/set-layer-cost/', {
            'layer_id': added.id, 'unit_cost': '30.00',
        }, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        added.refresh_from_db()
        self.assertEqual(added.unit_cost, Decimal('30.00'))
        self.assertEqual(added.unit_sell_price, Decimal('200.00'))
        self.large.refresh_from_db()
        self.assertEqual(self.large.cost, Decimal('20.00'))
        self.assertEqual(self.large.price, Decimal('150.00'))

    def test_a_new_size_with_no_stock_can_be_purchased(self):
        small_size = Size.objects.create(name='Small', code='S-NEW', is_active=True)
        small = ProductVariant.objects.create(
            product=self.product, size=small_size, sku='CLOTH-S-NEW',
            price=Decimal('90.00'), cost=Decimal('20.00'),
            stock_quantity=0, is_active=True,
        )
        self.client.force_authenticate(self.user)
        saved = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': small.id,
            'quantity': 5, 'price_mode': 'new', 'unit_sell_price': '110.00',
        }, format='json')
        self.assertEqual(saved.status_code, 201, saved.data)
        small.refresh_from_db()
        self.medium.refresh_from_db()
        self.assertEqual(small.stock_quantity, 5)
        self.assertEqual(self.medium.stock_quantity, 10)
        layer = StockLayer.objects.filter(variant=small).get()
        self.assertEqual(layer.unit_sell_price, Decimal('110.00'))
        self.assertEqual(layer.unit_cost, Decimal('20.00'))
        self.assertFalse(layer.sale_price_pending)
        sale = SaleService().create_sale(
            {'sale_type': 'pos', 'payment_method': 'cash', 'amount_paid': Decimal('550.00')},
            [{'product_id': self.product.id, 'variant_id': small.id, 'quantity': 5}],
            self.user,
        )
        charged = sum((item.subtotal for item in sale.items.all()), Decimal('0'))
        self.assertEqual(charged, Decimal('550.00'))
        self.assertNotIn('0718', str(saved.data))

    def test_the_variant_list_includes_a_new_empty_size(self):
        from utils.pagination import StandardResultsSetPagination

        configured = int(StandardResultsSetPagination.page_size or 10)
        extra = configured if configured < 200 else 1
        newest = None
        for index in range(extra):
            last = index == extra - 1
            size = Size.objects.create(
                name='ZZ Empty' if last else f'A{index:02d}',
                code=f'Z{index}' if last else f'A{index}',
                is_active=True,
            )
            newest = ProductVariant.objects.create(
                product=self.product, size=size, sku=f'CLOTH-N{index}',
                price=Decimal('40.00'), cost=Decimal('20.00'),
                stock_quantity=0, is_active=True,
            )
        self.client.force_authenticate(self.user)
        first_page = self.client.get('/api/products/variants/', {'product': self.product.id})
        self.assertEqual(first_page.status_code, 200, first_page.data)
        first_ids = [row['id'] for row in first_page.data['results']]
        full = self.client.get('/api/products/variants/', {
            'product': self.product.id, 'page_size': 200,
        })
        self.assertEqual(full.status_code, 200, full.data)
        ids = [row['id'] for row in full.data['results']]
        self.assertIn(newest.id, ids)
        if len(first_ids) < full.data['count']:
            self.assertNotIn(newest.id, first_ids)

    def test_purchases_off_blocks_a_new_empty_size(self):
        small_size = Size.objects.create(name='Tiny', code='T-NEW', is_active=True)
        small = ProductVariant.objects.create(
            product=self.product, size=small_size, sku='CLOTH-T-NEW',
            price=Decimal('90.00'), cost=Decimal('20.00'),
            stock_quantity=0, is_active=True,
        )
        self.client.force_authenticate(self.user)
        SettingsService.set('inventory', 'enable_stock_purchases', False)
        blocked = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': small.id,
            'quantity': 1, 'price_mode': 'old',
        }, format='json')
        self.assertEqual(blocked.status_code, 403)
        self.assertNotIn('0718', str(blocked.data))
        small.refresh_from_db()
        self.assertEqual(small.stock_quantity, 0)
        SettingsService.set('inventory', 'enable_stock_purchases', True)
        allowed = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': small.id,
            'quantity': 1, 'price_mode': 'old',
        }, format='json')
        self.assertEqual(allowed.status_code, 201, allowed.data)
        small.refresh_from_db()
        self.assertEqual(small.stock_quantity, 1)

    def test_staff_cannot_purchase_a_new_empty_size(self):
        small_size = Size.objects.create(name='Mini', code='M-NEW', is_active=True)
        small = ProductVariant.objects.create(
            product=self.product, size=small_size, sku='CLOTH-M-NEW',
            price=Decimal('90.00'), cost=Decimal('20.00'),
            stock_quantity=0, is_active=True,
        )
        self.client.force_authenticate(self.staff)
        denied = self.client.post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': small.id,
            'quantity': 3, 'price_mode': 'new', 'unit_sell_price': '110.00',
        }, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('0718', str(denied.data))
        anon = APIClient().post('/api/inventory/purchase/', {
            'product_id': self.product.id, 'variant_id': small.id, 'quantity': 3,
        }, format='json')
        self.assertEqual(anon.status_code, 401)
        small.refresh_from_db()
        self.assertEqual(small.stock_quantity, 0)

    def test_stress_two_hundred_pieces_start_an_empty_size(self):
        small_size = Size.objects.create(name='Bulk', code='B-NEW', is_active=True)
        small = ProductVariant.objects.create(
            product=self.product, size=small_size, sku='CLOTH-B-NEW',
            price=Decimal('90.00'), cost=Decimal('20.00'),
            stock_quantity=0, is_active=True,
        )
        self.inv.purchase_stock(
            product_id=self.product.id, variant_id=small.id, quantity=200,
            user=self.user, price_mode='new', unit_sell_price=Decimal('110.00'),
        )
        small.refresh_from_db()
        self.medium.refresh_from_db()
        self.large.refresh_from_db()
        self.assertEqual(small.stock_quantity, 200)
        self.assertEqual(self.medium.stock_quantity, 10)
        self.assertEqual(self.large.stock_quantity, 4)
        layer = StockLayer.objects.filter(variant=small).get()
        self.assertEqual(layer.qty_remaining, 200)
        self.assertEqual(layer.unit_sell_price, Decimal('110.00'))
