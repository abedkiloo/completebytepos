"""
Comprehensive integration tests for Product Views
Tests all API endpoints, error handling, edge cases
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from decimal import Decimal
from products.models import Category, Product, Size, Color, ProductVariant
from settings.models import Tenant, Branch
from suppliers.models import Supplier
import json
import io


class ProductViewSetTestCase(APITestCase):
    """Comprehensive tests for ProductViewSet API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        
        # Create regular user
        self.user = User.objects.create_user(
            username='testuser',
            email='user@test.com',
            password='test123'
        )
        
        # Create tenant and branch
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            code='TEST',
            country='Kenya',
            owner=self.superuser,
            created_by=self.superuser
        )
        
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            branch_code='BR001',
            name='Test Branch',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.superuser
        )
        
        # Create categories
        self.main_category = Category.objects.create(
            name='Test Category',
            description='Test category',
            is_active=True
        )
        
        self.sub_category = Category.objects.create(
            name='Test Subcategory',
            parent=self.main_category,
            description='Test subcategory',
            is_active=True
        )
        
        # Create sizes and colors
        self.size_small = Size.objects.create(
            name='Small',
            code='S',
            display_order=1,
            is_active=True
        )
        
        self.size_large = Size.objects.create(
            name='Large',
            code='L',
            display_order=2,
            is_active=True
        )
        
        self.color_red = Color.objects.create(
            name='Red',
            hex_code='#FF0000',
            is_active=True
        )
        
        self.color_blue = Color.objects.create(
            name='Blue',
            hex_code='#0000FF',
            is_active=True
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            contact_person='John Doe',
            email='supplier@test.com',
            phone='1234567890'
        )
        
        # Create test products
        self.test_product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            barcode='1234567890123',
            category=self.main_category,
            subcategory=self.sub_category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=100,
            low_stock_threshold=10,
            unit='piece',
            is_active=True,
            track_stock=True,
            supplier=self.supplier
        )
        
        # Setup API client
        self.client = APIClient()
    
    def get_auth_token(self, user):
        """Helper to get JWT token for a user"""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_list_products_authenticated(self):
        """Test listing products with authentication"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            products = response.data['results']
        else:
            products = response.data
        
        self.assertIsInstance(products, list)
        self.assertGreaterEqual(len(products), 1)
    
    def test_list_products_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_product_success(self):
        """Test successful product creation"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product_data = {
            'name': 'New Product',
            'sku': 'NEW-001',
            'barcode': '9876543210987',
            'category': self.main_category.id,
            'subcategory': self.sub_category.id,
            'price': '150.00',
            'cost': '75.00',
            'stock_quantity': 50,
            'low_stock_threshold': 5,
            'unit': 'piece',
            'is_active': True,
            'track_stock': True,
            'is_taxable': True,
            'supplier': self.supplier.id
        }
        
        response = self.client.post('/api/products/', product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify product was created
        self.assertTrue(Product.objects.filter(sku='NEW-001').exists())
        product = Product.objects.get(sku='NEW-001')
        self.assertEqual(product.name, 'New Product')
        self.assertEqual(product.price, Decimal('150.00'))
        self.assertEqual(product.cost, Decimal('75.00'))
    
    def test_create_product_duplicate_sku(self):
        """Test that duplicate SKU is rejected"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product_data = {
            'name': 'Duplicate',
            'sku': 'TEST-001',  # Already exists
            'category': self.main_category.id,
            'price': '100.00',
            'cost': '50.00'
        }
        
        response = self.client.post('/api/products/', product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_product_missing_required_fields(self):
        """Test that missing required fields are rejected"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product_data = {
            'category': self.main_category.id
            # Missing name, price, cost
        }
        
        response = self.client.post('/api/products/', product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_product_detail(self):
        """Test retrieving a single product"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/products/{self.test_product.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertEqual(response.data['name'], 'Test Product')
        self.assertEqual(response.data['sku'], 'TEST-001')
        self.assertEqual(float(response.data['price']), 100.00)
    
    def test_get_nonexistent_product(self):
        """Test retrieving non-existent product returns 404"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_update_product_success(self):
        """Test successful product update"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        update_data = {
            'name': 'Updated Product',
            'sku': 'TEST-001',
            'barcode': '1234567890123',
            'category': self.main_category.id,
            'price': '120.00',
            'cost': '60.00',
            'stock_quantity': 150,
            'is_active': True
        }
        
        response = self.client.put(
            f'/api/products/{self.test_product.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        self.test_product.refresh_from_db()
        self.assertEqual(self.test_product.name, 'Updated Product')
        self.assertEqual(self.test_product.price, Decimal('120.00'))
        self.assertEqual(self.test_product.stock_quantity, 150)
    
    def test_partial_update_product(self):
        """Test partial update (PATCH)"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        update_data = {
            'price': '110.00'
        }
        
        response = self.client.patch(
            f'/api/products/{self.test_product.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.test_product.refresh_from_db()
        self.assertEqual(self.test_product.price, Decimal('110.00'))
        # Other fields should remain unchanged
        self.assertEqual(self.test_product.name, 'Test Product')
    
    def test_delete_product(self):
        """Test product deletion"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product_to_delete = Product.objects.create(
            name='To Delete',
            sku='DELETE-001',
            category=self.main_category,
            price=Decimal('50.00'),
            cost=Decimal('25.00'),
            is_active=True
        )
        product_id = product_to_delete.id
        
        response = self.client.delete(f'/api/products/{product_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        self.assertFalse(Product.objects.filter(id=product_id).exists())
    
    def test_search_products(self):
        """Test product search endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/search/?q=Test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        products = response.data
        self.assertIsInstance(products, list)
        self.assertGreater(len(products), 0)
        # Should find test_product
        names = [p['name'] for p in products]
        self.assertIn('Test Product', names)
    
    def test_search_products_empty_query(self):
        """Test search with empty query"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/search/?q=')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
    
    def test_search_products_by_sku(self):
        """Test searching products by SKU"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/search/?q=TEST-001')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)
        self.assertEqual(response.data[0]['sku'], 'TEST-001')
    
    def test_filter_products_by_category(self):
        """Test filtering products by category"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/products/?category={self.main_category.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            products = response.data['results']
        else:
            products = response.data
        
        # All products should be in the specified category
        for product in products:
            self.assertEqual(product['category'], self.main_category.id)
    
    def test_filter_products_by_active_status(self):
        """Test filtering products by active status"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create an inactive product
        inactive_product = Product.objects.create(
            name='Inactive Product',
            sku='INACTIVE-001',
            category=self.main_category,
            price=Decimal('50.00'),
            cost=Decimal('25.00'),
            is_active=False
        )
        
        # Filter for active products
        response = self.client.get('/api/products/?is_active=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            products = response.data['results']
        else:
            products = response.data
        
        # All products should be active
        for product in products:
            self.assertTrue(product['is_active'])
        
        # Inactive product should not be in results
        skus = [p['sku'] for p in products]
        self.assertNotIn('INACTIVE-001', skus)
    
    def test_low_stock_products_endpoint(self):
        """Test low stock products endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create a low stock product
        low_stock_product = Product.objects.create(
            name='Low Stock Product',
            sku='LOW-001',
            category=self.main_category,
            price=Decimal('50.00'),
            cost=Decimal('25.00'),
            stock_quantity=5,  # Below threshold
            low_stock_threshold=10,
            track_stock=True,
            is_active=True
        )
        
        response = self.client.get('/api/products/low_stock/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        products = response.data
        self.assertIsInstance(products, list)
        # Should include low stock product
        skus = [p['sku'] for p in products]
        self.assertIn('LOW-001', skus)
    
    def test_out_of_stock_products_endpoint(self):
        """Test out of stock products endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create an out of stock product
        out_of_stock_product = Product.objects.create(
            name='Out of Stock Product',
            sku='OUT-001',
            category=self.main_category,
            price=Decimal('50.00'),
            cost=Decimal('25.00'),
            stock_quantity=0,
            track_stock=True,
            is_active=True
        )
        
        response = self.client.get('/api/products/out_of_stock/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        products = response.data
        self.assertIsInstance(products, list)
        # Should include out of stock product
        skus = [p['sku'] for p in products]
        self.assertIn('OUT-001', skus)
    
    def test_product_statistics_endpoint(self):
        """Test product statistics endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertIn('total_products', stats)
        self.assertIn('active_products', stats)
        self.assertIn('low_stock_products', stats)
        self.assertIn('out_of_stock_products', stats)
    
    def test_bulk_update_products(self):
        """Test bulk update endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product2 = Product.objects.create(
            name='Product 2',
            sku='BULK-002',
            category=self.main_category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        
        response = self.client.post(
            '/api/products/bulk_update/',
            {
                'product_ids': [self.test_product.id, product2.id],
                'update_data': {'is_active': False}
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('updated_count', response.data)
        self.assertEqual(response.data['updated_count'], 2)
        
        # Verify updates
        self.test_product.refresh_from_db()
        product2.refresh_from_db()
        self.assertFalse(self.test_product.is_active)
        self.assertFalse(product2.is_active)
    
    def test_bulk_update_empty_list(self):
        """Test bulk update with empty product list"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            '/api/products/bulk_update/',
            {
                'product_ids': [],
                'update_data': {'is_active': False}
            },
            format='json'
        )
        # Should handle gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    def test_bulk_delete_products(self):
        """Test bulk delete endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product_to_delete = Product.objects.create(
            name='To Delete',
            sku='BULK-DEL-001',
            category=self.main_category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        
        response = self.client.post(
            '/api/products/bulk_delete/',
            {'product_ids': [product_to_delete.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Product.objects.filter(id=product_to_delete.id).exists())
    
    def test_bulk_delete_no_ids(self):
        """Test bulk delete without product IDs"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            '/api/products/bulk_delete/',
            {'product_ids': []},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_bulk_activate_products(self):
        """Test bulk activate endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        inactive_product = Product.objects.create(
            name='Inactive',
            sku='BULK-ACT-001',
            category=self.main_category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=False
        )
        
        response = self.client.post(
            '/api/products/bulk_activate/',
            {'product_ids': [inactive_product.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        inactive_product.refresh_from_db()
        self.assertTrue(inactive_product.is_active)
    
    def test_bulk_deactivate_products(self):
        """Test bulk deactivate endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            '/api/products/bulk_deactivate/',
            {'product_ids': [self.test_product.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.test_product.refresh_from_db()
        self.assertFalse(self.test_product.is_active)
    
    def test_export_products_csv(self):
        """Test exporting products to CSV"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/export/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('products_export.csv', response['Content-Disposition'])
        
        # Verify CSV content
        content = response.content.decode('utf-8-sig')
        self.assertIn('SKU', content)
        self.assertIn('Name', content)
        self.assertIn('TEST-001', content)
    
    def test_import_products_csv_success(self):
        """Test successful CSV import"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        csv_content = """SKU,Name,Category,Price,Cost,Stock Quantity,Is Active
IMPORT-001,Imported Product,Test Category,100.00,50.00,10,true"""
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        
        response = self.client.post(
            '/api/products/import_csv/',
            {'file': csv_file},
            format='multipart'
        )
        
        # Should succeed or return appropriate status
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
    
    def test_import_products_csv_no_file(self):
        """Test CSV import without file"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post('/api/products/import_csv/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_filter_products_by_supplier(self):
        """Test filtering products by supplier"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/products/?supplier={self.supplier.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            products = response.data['results']
        else:
            products = response.data
        
        # All products should have the specified supplier
        for product in products:
            if 'supplier' in product and product['supplier']:
                self.assertEqual(product['supplier'], self.supplier.id)
    
    def test_filter_products_by_track_stock(self):
        """Test filtering products by track_stock"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/?track_stock=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            products = response.data['results']
        else:
            products = response.data
        
        # All products should track stock
        for product in products:
            self.assertTrue(product['track_stock'])
    
    def test_create_product_with_variants(self):
        """Test creating product with variants"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product_data = {
            'name': 'Variant Product',
            'sku': 'VAR-001',
            'category': self.main_category.id,
            'price': '200.00',
            'cost': '100.00',
            'has_variants': True,
            'available_sizes': [self.size_small.id, self.size_large.id],
            'available_colors': [self.color_red.id, self.color_blue.id],
            'is_active': True
        }
        
        response = self.client.post('/api/products/', product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        product = Product.objects.get(sku='VAR-001')
        self.assertTrue(product.has_variants)
        self.assertEqual(product.available_sizes.count(), 2)
        self.assertEqual(product.available_colors.count(), 2)
        
        # Variants should be created automatically
        variants = ProductVariant.objects.filter(product=product)
        self.assertEqual(variants.count(), 4)  # 2 sizes × 2 colors = 4 variants
    
    def test_product_pagination(self):
        """Test that product list supports pagination"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create multiple products
        for i in range(25):
            Product.objects.create(
                name=f'Product {i}',
                sku=f'PAG-{i:03d}',
                category=self.main_category,
                price=Decimal('100.00'),
                cost=Decimal('50.00'),
                is_active=True
            )
        
        response = self.client.get('/api/products/?page_size=10')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should have pagination if configured
        if 'results' in response.data:
            self.assertLessEqual(len(response.data['results']), 10)
            self.assertIn('count', response.data)
    
    def test_product_ordering(self):
        """Test product ordering"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create products with different names
        Product.objects.create(
            name='Zebra Product',
            sku='Z-001',
            category=self.main_category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        Product.objects.create(
            name='Apple Product',
            sku='A-001',
            category=self.main_category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        
        response = self.client.get('/api/products/?ordering=name')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            products = response.data['results']
        else:
            products = response.data
        
        # Products should be ordered by name
        if len(products) >= 2:
            names = [p['name'] for p in products]
            # First product should come before second alphabetically
            self.assertLessEqual(names[0], names[1])


class CategoryViewSetTestCase(APITestCase):
    """Tests for CategoryViewSet"""
    
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
        
        self.main_category = Category.objects.create(
            name='Main Category',
            is_active=True
        )
    
    def test_list_categories(self):
        """Test listing categories"""
        response = self.client.get('/api/products/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_category(self):
        """Test creating a category"""
        category_data = {
            'name': 'New Category',
            'description': 'A new category',
            'is_active': True
        }
        
        response = self.client.post('/api/products/categories/', category_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Category.objects.filter(name='New Category').exists())
    
    def test_get_category_products(self):
        """Test getting products in a category"""
        response = self.client.get(f'/api/products/categories/{self.main_category.id}/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class SizeViewSetTestCase(APITestCase):
    """Tests for SizeViewSet"""
    
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
    
    def test_list_sizes(self):
        """Test listing sizes"""
        response = self.client.get('/api/products/sizes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_size(self):
        """Test creating a size"""
        size_data = {
            'name': 'Extra Large',
            'code': 'XL',
            'display_order': 3,
            'is_active': True
        }
        
        response = self.client.post('/api/products/sizes/', size_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Size.objects.filter(code='XL').exists())


class ColorViewSetTestCase(APITestCase):
    """Tests for ColorViewSet"""
    
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
    
    def test_list_colors(self):
        """Test listing colors"""
        response = self.client.get('/api/products/colors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_color(self):
        """Test creating a color"""
        color_data = {
            'name': 'Green',
            'hex_code': '#00FF00',
            'is_active': True
        }
        
        response = self.client.post('/api/products/colors/', color_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Color.objects.filter(name='Green').exists())


class ProductVariantViewSetTestCase(APITestCase):
    """Tests for ProductVariantViewSet"""
    
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
        
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            code='TEST',
            owner=self.superuser,
            created_by=self.superuser
        )
        
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            has_variants=True
        )
        self.size = Size.objects.create(name='Small', code='S', is_active=True)
        self.color = Color.objects.create(name='Red', is_active=True)
    
    def test_list_variants(self):
        """Test listing variants"""
        ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            sku='TEST-001-S-RED',
            price=Decimal('100.00'),
            stock_quantity=10
        )
        
        response = self.client.get('/api/products/variants/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_variant(self):
        """Test creating a variant"""
        variant_data = {
            'product': self.product.id,
            'size': self.size.id,
            'color': self.color.id,
            'sku': 'TEST-001-S-RED',
            'price': '110.00',
            'stock_quantity': 20
        }
        
        response = self.client.post('/api/products/variants/', variant_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ProductVariant.objects.filter(sku='TEST-001-S-RED').exists())
    
    def test_filter_variants_by_product(self):
        """Test filtering variants by product"""
        variant = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            sku='TEST-001-S-RED',
            price=Decimal('100.00'),
            stock_quantity=10
        )
        
        response = self.client.get(f'/api/products/variants/?product={self.product.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            variants = response.data['results']
        else:
            variants = response.data
        
        # All variants should belong to the specified product
        for variant_data in variants:
            self.assertEqual(variant_data['product'], self.product.id)
