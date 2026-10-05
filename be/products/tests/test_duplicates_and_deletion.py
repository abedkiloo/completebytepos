"""Same product added twice is caught; admins remove items added in error."""

from decimal import Decimal
from io import BytesIO

from rest_framework import status

from inventory.models import StockMovement
from products.models import Category, Color, Product, ProductVariant, Size
from sales.models import Sale, SaleItem
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


def _product(name, sku, **extra):
    defaults = {'price': Decimal('100.00'), 'cost': Decimal('60.00'), 'stock_quantity': 0}
    defaults.update(extra)
    return Product.objects.create(name=name, sku=sku, **defaults)


class DuplicateProductTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Drinks', is_active=True)
        cls.soda = _product('Coca Cola 500ml', 'SODA-1', category=cls.category)

    def _create(self, name, sku):
        return self.client.post(
            '/api/products/',
            {'name': name, 'sku': sku, 'category': self.category.id, 'price': '100.00', 'cost': '60.00'},
            format='json',
        )

    def test_same_name_is_rejected_ignoring_case_and_spaces(self):
        response = self._create('  coca   COLA 500ml ', 'SODA-2')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        message = response.data['name'][0]
        self.assertIn('"Coca Cola 500ml" already exists (SKU SODA-1)', message)
        self.assertIn('instead of adding it again', message)
        self.assertEqual(Product.objects.filter(name__iexact='coca cola 500ml').count(), 1)

    def test_inactive_duplicate_suggests_reactivating(self):
        _product('Fanta 300ml', 'FANTA-OLD', is_active=False)
        response = self._create('Fanta 300ml', 'FANTA-NEW')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inactive', response.data['name'][0])
        self.assertIn('Reactivate it', response.data['name'][0])

    def test_new_name_is_saved_tidied(self):
        response = self._create('  Sprite   1L ', 'SPRITE-1')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Product.objects.get(sku='SPRITE-1').name, 'Sprite 1L')

    def test_renaming_onto_another_product_is_rejected(self):
        water = _product('Water 1L', 'WATER-1', category=self.category)
        response = self.client.patch(
            f'/api/products/{water.id}/', {'name': 'Coca Cola 500ml'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exists', response.data['name'][0])

    def test_existing_duplicates_can_still_be_edited(self):
        twin = _product('Coca Cola 500ml', 'SODA-TWIN', category=self.category)
        response = self.client.patch(
            f'/api/products/{twin.id}/',
            {'name': 'Coca Cola 500ml', 'description': 'Added twice by mistake'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_check_duplicate_endpoint_warns_while_typing(self):
        hit = self.client.get('/api/products/check_duplicate/', {'name': 'COCA cola 500ml'})
        self.assertEqual(hit.status_code, status.HTTP_200_OK)
        self.assertEqual(hit.data['duplicate']['id'], self.soda.id)
        self.assertIn('already exists', hit.data['message'])

        own = self.client.get(
            '/api/products/check_duplicate/', {'name': 'Coca Cola 500ml', 'exclude': self.soda.id}
        )
        self.assertIsNone(own.data['duplicate'])
        self.assertIsNone(
            self.client.get('/api/products/check_duplicate/', {'name': 'Pepsi'}).data['duplicate']
        )

    def test_csv_import_skips_rows_that_duplicate_a_name(self):
        csv_bytes = (
            'sku,name,price,cost\n'
            'SODA-CSV,coca cola 500ml,100,60\n'
            'SODA-1,Coca Cola 500ml,120,60\n'
            'JUICE-1,Mango Juice,80,40\n'
            'JUICE-2,Mango juice,80,40\n'
        ).encode()
        upload = BytesIO(csv_bytes)
        upload.name = 'products.csv'
        response = self.client.post('/api/products/import_csv/', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(response.data['updated_count'], 1)
        errors = ' '.join(response.data['errors'])
        self.assertIn('Row 2:', errors)
        self.assertIn('Row 5:', errors)
        self.assertFalse(Product.objects.filter(sku__in=['SODA-CSV', 'JUICE-2']).exists())


class AdminDeleteProductTests(SuperAdminAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Snacks', is_active=True)

    def test_admin_deletes_item_added_in_error(self):
        mistake = _product('Crisps 50g', 'CRISP-DUP', category=self.category)
        response = self.client.delete(f'/api/products/{mistake.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(pk=mistake.id).exists())

    def test_product_with_stock_is_kept(self):
        stocked = _product('Crisps 100g', 'CRISP-100', category=self.category, stock_quantity=4)
        response = self.client.delete(f'/api/products/{stocked.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('it still has 4 in stock', response.data['error'])
        self.assertIn('Deactivate it instead', response.data['error'])
        self.assertTrue(Product.objects.filter(pk=stocked.id).exists())

    def test_variant_stock_counts_as_stock(self):
        product = _product('T-shirt', 'TEE-1', category=self.category, has_variants=True)
        ProductVariant.objects.create(
            product=product,
            size=Size.objects.create(name='Medium', code='M'),
            color=Color.objects.create(name='Blue'),
            price=Decimal('100.00'), cost=Decimal('60.00'), stock_quantity=2,
        )
        product.refresh_from_db()
        product.stock_quantity = 0
        product.save(update_fields=['stock_quantity'])
        response = self.client.delete(f'/api/products/{product.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('2 in stock', response.data['error'])

    def test_sold_product_is_kept_so_sales_history_stays(self):
        sold = _product('Biscuits', 'BISC-1', category=self.category)
        sale = Sale.objects.create(
            status='completed', payment_method='cash', subtotal=Decimal('100.00'),
            tax_amount=Decimal('0'), discount_amount=Decimal('0'), total=Decimal('100.00'),
            amount_paid=Decimal('100.00'), cashier=self.admin,
        )
        SaleItem.objects.create(
            sale=sale, product=sold, quantity=1,
            unit_price=Decimal('100.00'), subtotal=Decimal('100.00'),
        )
        response = self.client.delete(f'/api/products/{sold.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sale items', response.data['error'])
        self.assertTrue(SaleItem.objects.filter(sale=sale).exists())

    def test_purchased_product_is_kept_even_after_stock_is_gone(self):
        bought = _product('Peanuts', 'NUTS-1', category=self.category)
        StockMovement.objects.create(product=bought, movement_type='purchase', quantity=5, user=self.admin)
        StockMovement.objects.create(product=bought, movement_type='adjustment', quantity=-5, user=self.admin)
        bought.refresh_from_db()
        self.assertEqual(bought.stock_quantity, 0)
        response = self.client.delete(f'/api/products/{bought.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('purchases', response.data['error'])

    def test_stock_corrections_are_removed_with_the_mistaken_item(self):
        mistake = _product('Popcorn', 'POP-DUP', category=self.category)
        StockMovement.objects.create(product=mistake, movement_type='adjustment', quantity=3, user=self.admin)
        StockMovement.objects.create(product=mistake, movement_type='adjustment', quantity=-3, user=self.admin)
        response = self.client.delete(f'/api/products/{mistake.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        self.assertFalse(StockMovement.objects.filter(product_id=mistake.id).exists())

    def test_bulk_delete_removes_mistakes_and_keeps_products_in_use(self):
        mistake = _product('Chocolate', 'CHOC-DUP', category=self.category)
        stocked = _product('Chocolate bar', 'CHOC-1', category=self.category, stock_quantity=9)
        response = self.client.post(
            '/api/products/bulk_delete/', {'product_ids': [mistake.id, stocked.id]}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['deleted_count'], 1)
        self.assertEqual(len(response.data['skipped']), 1)
        self.assertIn('Chocolate bar', response.data['skipped'][0])
        self.assertFalse(Product.objects.filter(pk=mistake.id).exists())
        self.assertTrue(Product.objects.filter(pk=stocked.id).exists())


class NonAdminCannotDeleteProductTests(ManagerAPITestCase):
    def test_manager_cannot_delete_even_an_unused_product(self):
        from products.deletion import ADMIN_ONLY_DELETE_MESSAGE

        mistake = _product('Gum', 'GUM-DUP')
        response = self.client.delete(f'/api/products/{mistake.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], ADMIN_ONLY_DELETE_MESSAGE)
        bulk = self.client.post('/api/products/bulk_delete/', {'product_ids': [mistake.id]}, format='json')
        self.assertEqual(bulk.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(pk=mistake.id).exists())
