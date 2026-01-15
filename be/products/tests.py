"""
Comprehensive tests for Product Management API
Tests: Create, Read, Update, Delete, List, Search, Variants, Categories
"""
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from decimal import Decimal
from .models import Category, Product, Size, Color, ProductVariant
from settings.models import Tenant, Branch


class ProductAPITestCase(TransactionTestCase):
    """Test cases for Product API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
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
        
        # Create a test product
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
            track_stock=True
        )
        
        # Setup API client
        self.client = APIClient()
    
    def get_auth_token(self, user):
        """Helper to get JWT token for a user"""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_list_products(self):
        """Test listing products"""
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
    
    def test_create_product(self):
        """Test creating a new product"""
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
            'is_taxable': True
        }
        
        response = self.client.post('/api/products/', product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify product was created
        self.assertTrue(Product.objects.filter(sku='NEW-001').exists())
        product = Product.objects.get(sku='NEW-001')
        self.assertEqual(product.name, 'New Product')
        self.assertEqual(product.price, Decimal('150.00'))
        self.assertEqual(product.cost, Decimal('75.00'))
    
    def test_create_product_with_variants(self):
        """Test creating a product with size and color variants"""
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
    
    def test_get_product(self):
        """Test retrieving a single product"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/products/{self.test_product.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertEqual(response.data['name'], 'Test Product')
        self.assertEqual(response.data['sku'], 'TEST-001')
        self.assertEqual(float(response.data['price']), 100.00)
    
    def test_update_product(self):
        """Test updating a product"""
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
        
        response = self.client.put(f'/api/products/{self.test_product.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        self.test_product.refresh_from_db()
        self.assertEqual(self.test_product.name, 'Updated Product')
        self.assertEqual(self.test_product.price, Decimal('120.00'))
        self.assertEqual(self.test_product.stock_quantity, 150)
    
    def test_delete_product(self):
        """Test deleting a product"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create a product to delete
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
        """Test searching products"""
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
    
    def test_filter_products_by_status(self):
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
    
    def test_low_stock_products(self):
        """Test getting low stock products"""
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
    
    def test_out_of_stock_products(self):
        """Test getting out of stock products"""
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
    
    def test_product_validation(self):
        """Test product creation validation"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Try to create product without required fields
        invalid_data = {
            'category': self.main_category.id
            # Missing name, price, cost
        }
        
        response = self.client.post('/api/products/', invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_duplicate_sku(self):
        """Test that duplicate SKUs are rejected"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product_data = {
            'name': 'Duplicate SKU Product',
            'sku': 'TEST-001',  # Already exists
            'category': self.main_category.id,
            'price': '100.00',
            'cost': '50.00'
        }
        
        response = self.client.post('/api/products/', product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_product_list_after_create(self):
        """Test that newly created product appears in list"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Get initial count
        initial_response = self.client.get('/api/products/')
        if 'results' in initial_response.data:
            initial_count = len(initial_response.data['results'])
        else:
            initial_count = len(initial_response.data)
        
        # Create new product
        product_data = {
            'name': 'List Test Product',
            'sku': 'LIST-001',
            'category': self.main_category.id,
            'price': '100.00',
            'cost': '50.00',
            'is_active': True
        }
        create_response = self.client.post('/api/products/', product_data, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        
        # List products again
        list_response = self.client.get('/api/products/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        
        if 'results' in list_response.data:
            products = list_response.data['results']
        else:
            products = list_response.data
        
        # Should have one more product
        self.assertGreaterEqual(len(products), initial_count + 1)
        
        # New product should be in the list
        skus = [p['sku'] for p in products]
        self.assertIn('LIST-001', skus)
    
    def test_product_statistics(self):
        """Test product statistics endpoint"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertIn('total_products', stats)
        self.assertIn('active_products', stats)
        self.assertIn('low_stock_count', stats)
        self.assertIn('out_of_stock_count', stats)
    
    def test_product_with_image(self):
        """Test creating product with image upload"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io
        
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            img_io.read(),
            content_type="image/jpeg"
        )
        
        product_data = {
            'name': 'Product with Image',
            'sku': 'IMG-001',
            'category': self.main_category.id,
            'price': '100.00',
            'cost': '50.00',
            'image': image_file
        }
        
        response = self.client.post('/api/products/', product_data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        product = Product.objects.get(sku='IMG-001')
        self.assertIsNotNone(product.image)
    
    def test_product_variants_creation(self):
        """Test that product variants are created correctly"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product_data = {
            'name': 'Variant Test Product',
            'sku': 'VAR-TEST-001',
            'category': self.main_category.id,
            'price': '100.00',
            'cost': '50.00',
            'has_variants': True,
            'available_sizes': [self.size_small.id],
            'available_colors': [self.color_red.id, self.color_blue.id]
        }
        
        response = self.client.post('/api/products/', product_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        product = Product.objects.get(sku='VAR-TEST-001')
        variants = ProductVariant.objects.filter(product=product)
        
        # Should have 2 variants (1 size × 2 colors)
        self.assertEqual(variants.count(), 2)
        
        # Check variant details
        for variant in variants:
            self.assertIn(variant.color, [self.color_red, self.color_blue])
            self.assertEqual(variant.size, self.size_small)
    
    def test_filter_products_by_subcategory(self):
        """Test filtering products by subcategory"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/products/?subcategory={self.sub_category.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_filter_products_by_supplier(self):
        """Test filtering products by supplier"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create product with supplier
        Product.objects.create(
            name='Supplier Product',
            sku='SUP-001',
            category=self.main_category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            supplier='Test Supplier'
        )
        
        response = self.client.get('/api/products/?supplier=Test Supplier')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_filter_products_by_track_stock(self):
        """Test filtering products by track_stock"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/?track_stock=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_bulk_update_products(self):
        """Test bulk updating products"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        product2 = Product.objects.create(
            name='Product 2',
            sku='BULK-002',
            category=self.main_category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
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
    
    def test_bulk_delete_products(self):
        """Test bulk deleting products"""
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
    
    def test_bulk_activate_products(self):
        """Test bulk activating products"""
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
        """Test bulk deactivating products"""
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
    
    def test_export_products(self):
        """Test exporting products to CSV"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/export/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('products_export.csv', response['Content-Disposition'])
    
    def test_list_categories(self):
        """Test listing categories"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_category(self):
        """Test creating a category"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        category_data = {
            'name': 'New Category',
            'description': 'A new category',
            'is_active': True
        }
        
        response = self.client.post('/api/products/categories/', category_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Category.objects.filter(name='New Category').exists())
    
    def test_get_category(self):
        """Test retrieving a single category"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/products/categories/{self.main_category.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Category')
    
    def test_update_category(self):
        """Test updating a category"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        update_data = {'name': 'Updated Category', 'description': 'Updated'}
        response = self.client.put(
            f'/api/products/categories/{self.main_category.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.main_category.refresh_from_db()
        self.assertEqual(self.main_category.name, 'Updated Category')
    
    def test_delete_category(self):
        """Test deleting a category"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        category_to_delete = Category.objects.create(name='To Delete')
        response = self.client.delete(f'/api/products/categories/{category_to_delete.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_get_category_products(self):
        """Test getting products in a category"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/products/categories/{self.main_category.id}/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_list_sizes(self):
        """Test listing sizes"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/sizes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_size(self):
        """Test creating a size"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        size_data = {
            'name': 'Extra Large',
            'code': 'XL',
            'display_order': 3,
            'is_active': True
        }
        
        response = self.client.post('/api/products/sizes/', size_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Size.objects.filter(code='XL').exists())
    
    def test_update_size(self):
        """Test updating a size"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        update_data = {'name': 'Medium', 'code': 'M'}
        response = self.client.put(
            f'/api/products/sizes/{self.size_small.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_delete_size(self):
        """Test deleting a size"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        size_to_delete = Size.objects.create(name='To Delete', code='TD')
        response = self.client.delete(f'/api/products/sizes/{size_to_delete.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_filter_sizes_by_active(self):
        """Test filtering sizes by active status"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/sizes/?is_active=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_list_colors(self):
        """Test listing colors"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/colors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_color(self):
        """Test creating a color"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        color_data = {
            'name': 'Green',
            'hex_code': '#00FF00',
            'is_active': True
        }
        
        response = self.client.post('/api/products/colors/', color_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Color.objects.filter(name='Green').exists())
    
    def test_update_color(self):
        """Test updating a color"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        update_data = {'name': 'Dark Red', 'hex_code': '#CC0000'}
        response = self.client.put(
            f'/api/products/colors/{self.color_red.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_delete_color(self):
        """Test deleting a color"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        color_to_delete = Color.objects.create(name='To Delete')
        response = self.client.delete(f'/api/products/colors/{color_to_delete.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_filter_colors_by_active(self):
        """Test filtering colors by active status"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/colors/?is_active=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_list_product_variants(self):
        """Test listing product variants"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create a variant
        variant = ProductVariant.objects.create(
            product=self.test_product,
            size=self.size_small,
            color=self.color_red,
            sku='TEST-001-S-RED',
            price=Decimal('100.00'),
            stock_quantity=10
        )
        
        response = self.client.get('/api/products/variants/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_product_variant(self):
        """Test creating a product variant"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        variant_data = {
            'product': self.test_product.id,
            'size': self.size_large.id,
            'color': self.color_blue.id,
            'sku': 'TEST-001-L-BLUE',
            'price': '110.00',
            'stock_quantity': 20
        }
        
        response = self.client.post('/api/products/variants/', variant_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ProductVariant.objects.filter(sku='TEST-001-L-BLUE').exists())
    
    def test_get_product_variant(self):
        """Test retrieving a single variant"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        variant = ProductVariant.objects.create(
            product=self.test_product,
            size=self.size_small,
            color=self.color_red,
            sku='TEST-001-S-RED',
            price=Decimal('100.00'),
            stock_quantity=10
        )
        
        response = self.client.get(f'/api/products/variants/{variant.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sku'], 'TEST-001-S-RED')
    
    def test_update_product_variant(self):
        """Test updating a product variant"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        variant = ProductVariant.objects.create(
            product=self.test_product,
            size=self.size_small,
            color=self.color_red,
            sku='TEST-001-S-RED',
            price=Decimal('100.00'),
            stock_quantity=10
        )
        
        update_data = {
            'product': self.test_product.id,
            'size': self.size_small.id,
            'color': self.color_red.id,
            'sku': 'TEST-001-S-RED',
            'price': '120.00',
            'stock_quantity': 15
        }
        
        response = self.client.put(
            f'/api/products/variants/{variant.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        variant.refresh_from_db()
        self.assertEqual(variant.price, Decimal('120.00'))
        self.assertEqual(variant.stock_quantity, 15)
    
    def test_delete_product_variant(self):
        """Test deleting a product variant"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        variant = ProductVariant.objects.create(
            product=self.test_product,
            size=self.size_small,
            color=self.color_red,
            sku='TEST-001-S-RED',
            price=Decimal('100.00'),
            stock_quantity=10
        )
        
        response = self.client.delete(f'/api/products/variants/{variant.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProductVariant.objects.filter(id=variant.id).exists())
    
    def test_filter_variants_by_product(self):
        """Test filtering variants by product"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        variant = ProductVariant.objects.create(
            product=self.test_product,
            size=self.size_small,
            color=self.color_red,
            sku='TEST-001-S-RED',
            price=Decimal('100.00'),
            stock_quantity=10
        )
        
        response = self.client.get(f'/api/products/variants/?product={self.test_product.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_search_products_empty_query(self):
        """Test search with empty query"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/products/search/?q=')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
    
    def test_bulk_update_invalid_data(self):
        """Test bulk update with invalid data"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            '/api/products/bulk_update/',
            {'product_ids': []},
            format='json'
        )
        # Should handle empty list gracefully or return error
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
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
