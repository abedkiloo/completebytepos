"""
Extended comprehensive tests for Product Services
Tests build_queryset methods and additional edge cases
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from decimal import Decimal
from products.models import Product, Category, Size, Color, ProductVariant
from suppliers.models import Supplier
from products.services import (
    ProductService, CategoryService, SizeService, ColorService, ProductVariantService
)
from settings.models import Tenant
from django.contrib.auth.models import User


class ProductServiceBuildQuerysetTestCase(TestCase):
    """Extended tests for ProductService build_queryset method"""
    
    def setUp(self):
        self.service = ProductService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
        )
        self.category = Category.objects.create(name='Test Category', is_active=True)
        self.subcategory = Category.objects.create(
            name='Test Subcategory',
            parent=self.category,
            is_active=True
        )
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            contact_person='John Doe',
            email='supplier@test.com',
            phone='1234567890'
        )
    
    def test_build_queryset_no_filters(self):
        """Test build_queryset with no filters"""
        queryset = self.service.build_queryset()
        self.assertIsInstance(queryset, QuerySet)
        self.assertGreaterEqual(queryset.count(), 0)
    
    def test_build_queryset_is_active_filter_string(self):
        """Test build_queryset with is_active filter as string"""
        Product.objects.create(
            name='Active Product',
            sku='ACT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        Product.objects.create(
            name='Inactive Product',
            sku='INACT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=False
        )
        
        queryset = self.service.build_queryset({'is_active': 'true'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'ACT-001')
        
        queryset = self.service.build_queryset({'is_active': 'false'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'INACT-001')
    
    def test_build_queryset_is_active_filter_boolean(self):
        """Test build_queryset with is_active filter as boolean"""
        Product.objects.create(
            name='Active Product',
            sku='ACT-002',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        
        queryset = self.service.build_queryset({'is_active': True})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'ACT-002')
    
    def test_build_queryset_category_filter(self):
        """Test build_queryset with category filter"""
        category2 = Category.objects.create(name='Category 2', is_active=True)
        Product.objects.create(
            name='Product 1',
            sku='CAT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        Product.objects.create(
            name='Product 2',
            sku='CAT-002',
            category=category2,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        
        queryset = self.service.build_queryset({'category': self.category.id})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'CAT-001')
    
    def test_build_queryset_subcategory_filter(self):
        """Test build_queryset with subcategory filter"""
        Product.objects.create(
            name='Sub Product',
            sku='SUB-001',
            category=self.category,
            subcategory=self.subcategory,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        Product.objects.create(
            name='No Sub Product',
            sku='SUB-002',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        
        queryset = self.service.build_queryset({'subcategory': self.subcategory.id})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'SUB-001')
    
    def test_build_queryset_low_stock_filter(self):
        """Test build_queryset with low_stock filter"""
        Product.objects.create(
            name='Low Stock',
            sku='LOW-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=5,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True
        )
        Product.objects.create(
            name='Normal Stock',
            sku='NORM-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=50,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True
        )
        
        queryset = self.service.build_queryset({'low_stock': 'true'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'LOW-001')
    
    def test_build_queryset_out_of_stock_filter(self):
        """Test build_queryset with out_of_stock filter"""
        Product.objects.create(
            name='Out of Stock',
            sku='OUT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=0,
            track_stock=True,
            is_active=True
        )
        Product.objects.create(
            name='In Stock',
            sku='IN-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=10,
            track_stock=True,
            is_active=True
        )
        
        queryset = self.service.build_queryset({'out_of_stock': 'true'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'OUT-001')
    
    def test_build_queryset_track_stock_filter(self):
        """Test build_queryset with track_stock filter"""
        Product.objects.create(
            name='Track Stock',
            sku='TRACK-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            track_stock=True
        )
        Product.objects.create(
            name='No Track Stock',
            sku='NOTRACK-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            track_stock=False
        )
        
        queryset = self.service.build_queryset({'track_stock': 'true'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'TRACK-001')
    
    def test_build_queryset_supplier_filter_by_id(self):
        """Test build_queryset with supplier filter by ID"""
        supplier2 = Supplier.objects.create(
            name='Supplier 2',
            contact_person='Jane Doe',
            email='supplier2@test.com',
            phone='0987654321'
        )
        Product.objects.create(
            name='Product 1',
            sku='SUP-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            supplier=self.supplier
        )
        Product.objects.create(
            name='Product 2',
            sku='SUP-002',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            supplier=supplier2
        )
        
        queryset = self.service.build_queryset({'supplier': self.supplier.id})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'SUP-001')
    
    def test_build_queryset_supplier_filter_by_name_legacy(self):
        """Test build_queryset with supplier filter by name (legacy)"""
        Product.objects.create(
            name='Legacy Product',
            sku='LEG-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            supplier_name='Legacy Supplier'
        )
        
        queryset = self.service.build_queryset({'supplier': 'Legacy Supplier'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'LEG-001')
    
    def test_build_queryset_invalid_category(self):
        """Test build_queryset with invalid category ID"""
        queryset = self.service.build_queryset({'category': 'invalid'})
        self.assertEqual(queryset.count(), 0)
    
    def test_build_queryset_invalid_subcategory(self):
        """Test build_queryset with invalid subcategory ID"""
        queryset = self.service.build_queryset({'subcategory': 'invalid'})
        self.assertEqual(queryset.count(), 0)
    
    def test_build_queryset_multiple_filters(self):
        """Test build_queryset with multiple filters"""
        Product.objects.create(
            name='Match All',
            sku='MULT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=5,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True
        )
        Product.objects.create(
            name='No Match',
            sku='MULT-002',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=50,
            track_stock=True,
            is_active=True
        )
        
        queryset = self.service.build_queryset({
            'category': self.category.id,
            'low_stock': 'true',
            'is_active': True
        })
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'MULT-001')
    
    def test_create_product_duplicate_barcode(self):
        """Test product creation with duplicate barcode fails"""
        Product.objects.create(
            name='Existing',
            sku='BAR-001',
            barcode='1234567890',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        
        data = {
            'name': 'Duplicate',
            'sku': 'BAR-002',
            'barcode': '1234567890',  # Duplicate
            'category': self.category,
            'price': Decimal('100.00'),
            'cost': Decimal('50.00')
        }
        
        with self.assertRaises(ValidationError):
            self.service.create_product(data)
    
    def test_create_product_invalid_supplier(self):
        """Test product creation with invalid supplier fails"""
        data = {
            'name': 'Product',
            'sku': 'SUP-001',
            'category': self.category,
            'price': Decimal('100.00'),
            'cost': Decimal('50.00'),
            'supplier': 99999  # Non-existent supplier
        }
        
        with self.assertRaises(ValidationError):
            self.service.create_product(data)
    
    def test_update_product_with_variants(self):
        """Test updating product with variant changes"""
        size = Size.objects.create(name='Small', code='S', is_active=True)
        color = Color.objects.create(name='Red', is_active=True)
        
        product = Product.objects.create(
            name='Variant Product',
            sku='VAR-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            has_variants=False
        )
        
        # Update to enable variants
        updated = self.service.update_product(
            product,
            {'has_variants': True},
            sizes=[size.id],
            colors=[color.id]
        )
        
        self.assertTrue(updated.has_variants)
        variants = ProductVariant.objects.filter(product=updated)
        self.assertEqual(variants.count(), 1)
    
    def test_bulk_update_empty_list(self):
        """Test bulk update with empty list"""
        updated = self.service.bulk_update_products([], {'is_active': False})
        self.assertEqual(updated, 0)
    
    def test_bulk_delete_empty_list(self):
        """Test bulk delete with empty list"""
        deleted = self.service.bulk_delete_products([])
        self.assertEqual(deleted, 0)
    
    def test_export_products_with_queryset(self):
        """Test export with specific queryset"""
        Product.objects.create(
            name='Export 1',
            sku='EXP-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        Product.objects.create(
            name='Export 2',
            sku='EXP-002',
            category=self.category,
            price=Decimal('200.00'),
            cost=Decimal('100.00')
        )
        
        queryset = Product.objects.filter(sku='EXP-001')
        csv_data = self.service.export_products_to_csv(queryset)
        self.assertIn('EXP-001', csv_data)
        self.assertNotIn('EXP-002', csv_data)
    
    def test_get_product_statistics_error_handling(self):
        """Test get_product_statistics handles errors gracefully"""
        stats = self.service.get_product_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn('total_products', stats)
        self.assertIn('active_products', stats)
        self.assertIn('low_stock_products', stats)
        self.assertIn('out_of_stock_products', stats)


class CategoryServiceBuildQuerysetTestCase(TestCase):
    """Tests for CategoryService build_queryset method"""
    
    def setUp(self):
        self.service = CategoryService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
        )
        self.parent = Category.objects.create(name='Parent', is_active=True)
        self.child1 = Category.objects.create(name='Child 1', parent=self.parent, is_active=True)
        self.child2 = Category.objects.create(name='Child 2', parent=self.parent, is_active=True)
        Category.objects.create(name='Inactive', is_active=False)
    
    def test_build_queryset_no_filters(self):
        """Test build_queryset with no filters"""
        queryset = self.service.build_queryset()
        self.assertGreaterEqual(queryset.count(), 4)
    
    def test_build_queryset_is_active_filter(self):
        """Test build_queryset with is_active filter"""
        queryset = self.service.build_queryset({'is_active': 'true'})
        self.assertEqual(queryset.count(), 3)  # Parent + 2 children
    
    def test_build_queryset_parent_filter(self):
        """Test build_queryset with parent filter"""
        queryset = self.service.build_queryset({'parent': self.parent.id})
        self.assertEqual(queryset.count(), 2)  # 2 children
    
    def test_build_queryset_invalid_parent(self):
        """Test build_queryset with invalid parent ID"""
        queryset = self.service.build_queryset({'parent': 'invalid'})
        self.assertEqual(queryset.count(), 0)
    
    def test_get_category_products(self):
        """Test get_category_products method"""
        product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            category=self.parent,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        Product.objects.create(
            name='Inactive Product',
            sku='TEST-002',
            category=self.parent,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=False
        )
        
        products = self.service.get_category_products(self.parent.id, active_only=True)
        self.assertEqual(products.count(), 1)
        self.assertEqual(products.first().sku, 'TEST-001')
        
        products_all = self.service.get_category_products(self.parent.id, active_only=False)
        self.assertEqual(products_all.count(), 2)


class SizeServiceBuildQuerysetTestCase(TestCase):
    """Tests for SizeService build_queryset method"""
    
    def setUp(self):
        self.service = SizeService()
    
    def test_build_queryset_no_filters(self):
        """Test build_queryset with no filters"""
        Size.objects.create(name='Small', code='S', is_active=True)
        queryset = self.service.build_queryset()
        self.assertGreaterEqual(queryset.count(), 1)
    
    def test_build_queryset_is_active_filter(self):
        """Test build_queryset with is_active filter"""
        Size.objects.create(name='Active', code='A', is_active=True)
        Size.objects.create(name='Inactive', code='I', is_active=False)
        
        queryset = self.service.build_queryset({'is_active': 'true'})
        self.assertEqual(queryset.count(), 1)


class ColorServiceBuildQuerysetTestCase(TestCase):
    """Tests for ColorService build_queryset method"""
    
    def setUp(self):
        self.service = ColorService()
    
    def test_build_queryset_no_filters(self):
        """Test build_queryset with no filters"""
        Color.objects.create(name='Red', is_active=True)
        queryset = self.service.build_queryset()
        self.assertGreaterEqual(queryset.count(), 1)
    
    def test_build_queryset_is_active_filter(self):
        """Test build_queryset with is_active filter"""
        Color.objects.create(name='Active', is_active=True)
        Color.objects.create(name='Inactive', is_active=False)
        
        queryset = self.service.build_queryset({'is_active': 'true'})
        self.assertEqual(queryset.count(), 1)


class ProductVariantServiceBuildQuerysetTestCase(TestCase):
    """Tests for ProductVariantService build_queryset method"""
    
    def setUp(self):
        self.service = ProductVariantService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
        )
        self.category = Category.objects.create(name='Test Category')
        self.product1 = Product.objects.create(
            name='Product 1',
            sku='PROD-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        self.product2 = Product.objects.create(
            name='Product 2',
            sku='PROD-002',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        self.size = Size.objects.create(name='Small', code='S', is_active=True)
        self.color = Color.objects.create(name='Red', is_active=True)
    
    def test_build_queryset_no_filters(self):
        """Test build_queryset with no filters"""
        ProductVariant.objects.create(
            product=self.product1,
            size=self.size,
            color=self.color,
            sku='VAR-001',
            price=Decimal('100.00')
        )
        queryset = self.service.build_queryset()
        self.assertGreaterEqual(queryset.count(), 1)
    
    def test_build_queryset_product_filter(self):
        """Test build_queryset with product filter"""
        variant1 = ProductVariant.objects.create(
            product=self.product1,
            size=self.size,
            color=self.color,
            sku='VAR-001',
            price=Decimal('100.00')
        )
        ProductVariant.objects.create(
            product=self.product2,
            size=self.size,
            color=self.color,
            sku='VAR-002',
            price=Decimal('100.00')
        )
        
        queryset = self.service.build_queryset({'product': self.product1.id})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'VAR-001')
    
    def test_build_queryset_is_active_filter(self):
        """Test build_queryset with is_active filter"""
        ProductVariant.objects.create(
            product=self.product1,
            size=self.size,
            color=self.color,
            sku='VAR-001',
            price=Decimal('100.00'),
            is_active=True
        )
        ProductVariant.objects.create(
            product=self.product1,
            size=self.size,
            color=self.color,
            sku='VAR-002',
            price=Decimal('100.00'),
            is_active=False
        )
        
        queryset = self.service.build_queryset({'is_active': 'true'})
        self.assertEqual(queryset.count(), 1)
    
    def test_build_queryset_invalid_product(self):
        """Test build_queryset with invalid product ID"""
        queryset = self.service.build_queryset({'product': 'invalid'})
        self.assertEqual(queryset.count(), 0)
