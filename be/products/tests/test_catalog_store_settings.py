"""Product catalog rules driven by StoreSettings (sales vs manager pricing)."""

from decimal import Decimal

from products.models import Category, Product
from settings.models import StoreSettings
from utils.tests.api_test_base import ManagerAPITestCase, SalesAPITestCase


class CatalogStoreSettingsProductTests(SalesAPITestCase):
    """Sales staff catalog create/update respects store settings."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Catalog Cat', is_active=True)

    def setUp(self):
        super().setUp()
        store = StoreSettings.load()
        store.allow_sales_add_products = True
        store.sales_catalog_skip_pricing = True
        store.save()

    def test_sales_create_product_strips_pricing(self):
        response = self.client.post(
            '/api/products/',
            {
                'name': 'Sales Added Item',
                'category': self.category.id,
                'selling_price': '250.00',
                'mrp': '300.00',
                'cost': '100.00',
                'stock_quantity': 5,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(pk=response.data['id'])
        self.assertEqual(product.price, Decimal('0'))
        self.assertEqual(product.mrp, Decimal('0'))

    def test_sales_can_update_catalog_fields_not_pricing(self):
        product = Product.objects.create(
            name='Old Name',
            sku='CAT-001',
            category=self.category,
            price=Decimal('0'),
            mrp=Decimal('0'),
            cost=Decimal('0'),
            stock_quantity=1,
        )
        response = self.client.patch(
            f'/api/products/{product.id}/',
            {'name': 'New Name', 'selling_price': '250.00'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.name, 'New Name')
        self.assertEqual(product.price, Decimal('0'))

    def test_sales_csv_import_strips_pricing(self):
        import io

        csv_body = (
            'name,sku,category,selling_price,cost\n'
            'Imported Item,IMP-001,Catalog Cat,500.00,100.00\n'
        )
        file = io.BytesIO(csv_body.encode('utf-8'))
        file.name = 'products.csv'
        response = self.client.post(
            '/api/products/import_csv/',
            {'file': file},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        product = Product.objects.get(sku='IMP-001')
        self.assertEqual(product.price, Decimal('0'))
        self.assertEqual(product.name, 'Imported Item')


class ManagerPricingWithStoreSettingsTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Mgr Cat', is_active=True)

    def setUp(self):
        super().setUp()
        store = StoreSettings.load()
        store.allow_sales_add_products = True
        store.sales_catalog_skip_pricing = True
        store.save()

    def test_manager_create_product_keeps_pricing(self):
        response = self.client.post(
            '/api/products/',
            {
                'name': 'Manager Priced Item',
                'category': self.category.id,
                'selling_price': '150.00',
                'mrp': '180.00',
                'cost': '80.00',
                'stock_quantity': 10,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(pk=response.data['id'])
        self.assertEqual(product.price, Decimal('150.00'))
        self.assertEqual(product.mrp, Decimal('180.00'))
