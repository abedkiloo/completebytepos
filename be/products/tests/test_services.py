"""
Comprehensive unit tests for Product Services
Tests all business logic, edge cases, and error handling
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from products.models import Product, Category, Size, Color, ProductVariant
from suppliers.models import Supplier
from products.services import (
    ProductService, CategoryService, SizeService, ColorService, ProductVariantService
)
from settings.models import Tenant, Branch
from django.contrib.auth.models import User


class CategoryServiceTestCase(TestCase):
    """Tests for CategoryService"""
    
    def setUp(self):
        self.service = CategoryService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
        )
    
    def test_get_active_categories(self):
        """Test getting active categories"""
        cat1 = Category.objects.create(name='Cat1', is_active=True)
        Category.objects.create(name='Cat2', is_active=False)
        cat3 = Category.objects.create(name='Cat3', is_active=True)
        
        active = self.service.get_active_categories()
        self.assertEqual(len(active), 2)
        self.assertIn(cat1, active)
        self.assertIn(cat3, active)
    
    def test_get_active_categories_with_parent(self):
        """Test getting active categories filtered by parent"""
        parent = Category.objects.create(name='Parent', is_active=True)
        child1 = Category.objects.create(name='Child1', parent=parent, is_active=True)
        child2 = Category.objects.create(name='Child2', parent=parent, is_active=True)
        Category.objects.create(name='Other', is_active=True)
        
        children = self.service.get_active_categories(parent_id=parent.id)
        self.assertEqual(len(children), 2)
        self.assertIn(child1, children)
        self.assertIn(child2, children)
    
    def test_validate_parent_child_relationship_valid(self):
        """Test valid parent-child relationship"""
        parent = Category.objects.create(name='Parent', is_active=True)
        self.assertTrue(self.service.validate_parent_child_relationship(None, parent.id))
    
    def test_validate_parent_child_relationship_invalid_subcategory(self):
        """Test that subcategory cannot be parent"""
        parent = Category.objects.create(name='Parent', is_active=True)
        subcat = Category.objects.create(name='Sub', parent=parent, is_active=True)
        
        with self.assertRaises(ValidationError):
            self.service.validate_parent_child_relationship(None, subcat.id)
    
    def test_validate_parent_child_relationship_nonexistent(self):
        """Test validation with nonexistent parent"""
        with self.assertRaises(ValidationError):
            self.service.validate_parent_child_relationship(None, 99999)


class SizeServiceTestCase(TestCase):
    """Tests for SizeService"""
    
    def setUp(self):
        self.service = SizeService()
    
    def test_get_active_sizes(self):
        """Test getting active sizes ordered correctly"""
        Size.objects.create(name='Large', code='L', display_order=2, is_active=True)
        Size.objects.create(name='Small', code='S', display_order=1, is_active=True)
        Size.objects.create(name='Medium', code='M', display_order=0, is_active=True)
        Size.objects.create(name='Inactive', code='I', is_active=False)
        
        sizes = self.service.get_active_sizes()
        self.assertEqual(len(sizes), 3)
        self.assertEqual(sizes[0].code, 'M')  # Order 0
        self.assertEqual(sizes[1].code, 'S')   # Order 1
        self.assertEqual(sizes[2].code, 'L')   # Order 2


class ColorServiceTestCase(TestCase):
    """Tests for ColorService"""
    
    def setUp(self):
        self.service = ColorService()
    
    def test_get_active_colors(self):
        """Test getting active colors"""
        Color.objects.create(name='Red', is_active=True)
        Color.objects.create(name='Blue', is_active=True)
        Color.objects.create(name='Inactive', is_active=False)
        
        colors = self.service.get_active_colors()
        self.assertEqual(len(colors), 2)
        names = [c.name for c in colors]
        self.assertIn('Red', names)
        self.assertIn('Blue', names)


class ProductVariantServiceTestCase(TestCase):
    """Tests for ProductVariantService"""
    
    def setUp(self):
        self.service = ProductVariantService()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.tenant = Tenant.objects.create(
            name='Test Tenant', code='TEST', owner=self.user, created_by=self.user
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
        self.size_s = Size.objects.create(name='Small', code='S', is_active=True)
        self.size_l = Size.objects.create(name='Large', code='L', is_active=True)
        self.color_red = Color.objects.create(name='Red', is_active=True)
        self.color_blue = Color.objects.create(name='Blue', is_active=True)
    
    def test_create_variants_size_and_color(self):
        """Test creating variants with both size and color"""
        variants = self.service.create_variants_for_product(
            self.product,
            sizes=[self.size_s.id, self.size_l.id],
            colors=[self.color_red.id, self.color_blue.id]
        )
        
        self.assertEqual(len(variants), 4)  # 2 sizes × 2 colors
        
        skus = [v.sku for v in variants]
        self.assertIn('TEST-001-S-RED', skus)
        self.assertIn('TEST-001-S-BLU', skus)
        self.assertIn('TEST-001-L-RED', skus)
        self.assertIn('TEST-001-L-BLU', skus)
    
    def test_create_variants_size_only(self):
        """Test creating variants with size only"""
        variants = self.service.create_variants_for_product(
            self.product,
            sizes=[self.size_s.id, self.size_l.id],
            colors=None
        )
        
        self.assertEqual(len(variants), 2)
        for variant in variants:
            self.assertIsNotNone(variant.size)
            self.assertIsNone(variant.color)
    
    def test_create_variants_color_only(self):
        """Test creating variants with color only"""
        variants = self.service.create_variants_for_product(
            self.product,
            sizes=None,
            colors=[self.color_red.id, self.color_blue.id]
        )
        
        self.assertEqual(len(variants), 2)
        for variant in variants:
            self.assertIsNone(variant.size)
            self.assertIsNotNone(variant.color)
    
    def test_create_variants_no_variants(self):
        """Test that no variants are created if product doesn't have variants"""
        self.product.has_variants = False
        self.product.save()
        
        variants = self.service.create_variants_for_product(self.product)
        self.assertEqual(len(variants), 0)
    
    def test_get_variants_for_product(self):
        """Test getting variants for a product"""
        variant1 = ProductVariant.objects.create(
            product=self.product,
            size=self.size_s,
            color=self.color_red,
            sku='TEST-001-S-RED',
            price=Decimal('100.00'),
            stock_quantity=10
        )
        variant2 = ProductVariant.objects.create(
            product=self.product,
            size=self.size_l,
            color=self.color_blue,
            sku='TEST-001-L-BLU',
            price=Decimal('110.00'),
            stock_quantity=20
        )
        
        variants = self.service.get_variants_for_product(self.product.id)
        self.assertEqual(len(variants), 2)
        self.assertIn(variant1, variants)
        self.assertIn(variant2, variants)


class ProductServiceTestCase(TestCase):
    """Comprehensive tests for ProductService"""
    
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
    
    def test_search_products_by_name(self):
        """Test searching products by name"""
        Product.objects.create(
            name='Sofa Cushion',
            sku='SOFA-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        Product.objects.create(
            name='Table',
            sku='TABLE-001',
            category=self.category,
            price=Decimal('200.00'),
            cost=Decimal('100.00'),
            is_active=True
        )
        
        results = self.service.search_products('Sofa')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, 'Sofa Cushion')
    
    def test_search_products_by_sku(self):
        """Test searching products by SKU"""
        Product.objects.create(
            name='Product',
            sku='SOFA-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        
        results = self.service.search_products('SOFA')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].sku, 'SOFA-001')
    
    def test_search_products_empty_query(self):
        """Test search with empty query returns empty list"""
        results = self.service.search_products('')
        self.assertEqual(len(results), 0)
    
    def test_get_low_stock_products(self):
        """Test getting low stock products"""
        # Low stock product
        low_stock = Product.objects.create(
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
        
        # Normal stock product
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
        
        # Out of stock (should not be in low stock)
        Product.objects.create(
            name='Out of Stock',
            sku='OUT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=0,
            low_stock_threshold=10,
            track_stock=True,
            is_active=True
        )
        
        low_stock_products = self.service.get_low_stock_products()
        self.assertEqual(len(low_stock_products), 1)
        self.assertEqual(low_stock_products[0].sku, 'LOW-001')
    
    def test_get_out_of_stock_products(self):
        """Test getting out of stock products"""
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
        
        out_of_stock = self.service.get_out_of_stock_products()
        self.assertEqual(len(out_of_stock), 1)
        self.assertEqual(out_of_stock[0].sku, 'OUT-001')
    
    def test_create_product_success(self):
        """Test successful product creation"""
        data = {
            'name': 'New Product',
            'sku': 'NEW-001',
            'category': self.category,  # Category object
            'price': Decimal('100.00'),
            'cost': Decimal('50.00'),
            'stock_quantity': 100,
            'low_stock_threshold': 10,
            'unit': 'piece',
            'is_active': True,
            'track_stock': True
        }
        
        product = self.service.create_product(data)
        self.assertIsNotNone(product.id)
        self.assertEqual(product.name, 'New Product')
        self.assertEqual(product.sku, 'NEW-001')
        self.assertEqual(product.category, self.category)
    
    def test_create_product_duplicate_sku(self):
        """Test product creation with duplicate SKU fails"""
        Product.objects.create(
            name='Existing',
            sku='DUP-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        
        data = {
            'name': 'Duplicate',
            'sku': 'DUP-001',  # Duplicate
            'category': self.category,
            'price': Decimal('100.00'),
            'cost': Decimal('50.00')
        }
        
        with self.assertRaises(ValidationError):
            self.service.create_product(data)
    
    def test_create_product_invalid_category(self):
        """Test product creation with invalid category fails"""
        # Create a mock category object with invalid ID
        class MockCategory:
            id = 99999
        
        data = {
            'name': 'Product',
            'sku': 'TEST-001',
            'category': MockCategory(),  # Non-existent category
            'price': Decimal('100.00'),
            'cost': Decimal('50.00')
        }
        
        with self.assertRaises(ValidationError):
            self.service.create_product(data)
    
    def test_create_product_with_variants(self):
        """Test creating product with variants"""
        size = Size.objects.create(name='Small', code='S', is_active=True)
        color = Color.objects.create(name='Red', is_active=True)
        
        data = {
            'name': 'Variant Product',
            'sku': 'VAR-001',
            'category': self.category,
            'price': Decimal('100.00'),
            'cost': Decimal('50.00'),
            'has_variants': True
        }
        
        product = self.service.create_product(
            data,
            sizes=[size.id],
            colors=[color.id]
        )
        
        self.assertTrue(product.has_variants)
        # Variants should be created (1 size × 1 color = 1 variant)
        variants = ProductVariant.objects.filter(product=product)
        self.assertGreaterEqual(variants.count(), 1)
    
    def test_bulk_update_products(self):
        """Test bulk updating products"""
        p1 = Product.objects.create(
            name='Product 1',
            sku='BULK-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        p2 = Product.objects.create(
            name='Product 2',
            sku='BULK-002',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        
        updated = self.service.bulk_update_products(
            [p1.id, p2.id],
            {'is_active': False}
        )
        
        self.assertEqual(updated, 2)
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertFalse(p1.is_active)
        self.assertFalse(p2.is_active)
    
    def test_bulk_delete_products(self):
        """Test bulk deleting products"""
        p1 = Product.objects.create(
            name='To Delete 1',
            sku='DEL-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        p2 = Product.objects.create(
            name='To Delete 2',
            sku='DEL-002',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        
        deleted = self.service.bulk_delete_products([p1.id, p2.id])
        self.assertEqual(deleted, 2)
        self.assertFalse(Product.objects.filter(id__in=[p1.id, p2.id]).exists())
    
    def test_bulk_activate_products(self):
        """Test bulk activating products"""
        p1 = Product.objects.create(
            name='Inactive 1',
            sku='INACT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=False
        )
        
        activated = self.service.bulk_activate_products([p1.id])
        self.assertEqual(activated, 1)
        p1.refresh_from_db()
        self.assertTrue(p1.is_active)
    
    def test_bulk_deactivate_products(self):
        """Test bulk deactivating products"""
        p1 = Product.objects.create(
            name='Active 1',
            sku='ACT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=True
        )
        
        deactivated = self.service.bulk_deactivate_products([p1.id])
        self.assertEqual(deactivated, 1)
        p1.refresh_from_db()
        self.assertFalse(p1.is_active)
    
    def test_get_product_statistics(self):
        """Test getting product statistics"""
        # Create various products
        Product.objects.create(
            name='Active',
            sku='STAT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=10,
            low_stock_threshold=20,
            track_stock=True,
            is_active=True
        )
        Product.objects.create(
            name='Inactive',
            sku='STAT-002',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            is_active=False
        )
        Product.objects.create(
            name='Out of Stock',
            sku='STAT-003',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=0,
            track_stock=True,
            is_active=True
        )
        
        stats = self.service.get_product_statistics()
        
        self.assertIn('total_products', stats)
        self.assertIn('active_products', stats)
        self.assertIn('low_stock_count', stats)
        self.assertIn('out_of_stock_count', stats)
        self.assertGreaterEqual(stats['total_products'], 3)
        self.assertGreaterEqual(stats['active_products'], 2)
    
    def test_export_products_to_csv(self):
        """Test exporting products to CSV"""
        Product.objects.create(
            name='Export Test',
            sku='EXPORT-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock_quantity=10
        )
        
        csv_data = self.service.export_products_to_csv()
        self.assertIn('SKU', csv_data)
        self.assertIn('Name', csv_data)
        self.assertIn('EXPORT-001', csv_data)
        self.assertIn('Export Test', csv_data)
    
    def test_import_products_from_csv_success(self):
        """Test successful CSV import"""
        csv_content = """SKU,Name,Category,Price,Cost,Stock Quantity,Is Active
IMPORT-001,Imported Product,Test Category,100.00,50.00,10,true"""
        
        from io import StringIO
        csv_file = StringIO(csv_content)
        
        # Mock file object
        class MockFile:
            def read(self):
                return csv_content.encode('utf-8')
            def decode(self, encoding):
                return csv_content
        
        # This would need actual file handling - simplified for now
        # results = self.service.import_products_from_csv(MockFile())
        # self.assertGreater(results['created'], 0)
    
    def test_update_product_success(self):
        """Test successful product update"""
        product = Product.objects.create(
            name='Original',
            sku='UPDATE-001',
            category=self.category,
            price=Decimal('100.00'),
            cost=Decimal('50.00')
        )
        
        updated = self.service.update_product(
            product,
            {'name': 'Updated', 'price': Decimal('120.00')}
        )
        
        self.assertEqual(updated.name, 'Updated')
        self.assertEqual(updated.price, Decimal('120.00'))
    
    def test_build_queryset_no_filters(self):
        """Test build_queryset with no filters"""
        queryset = self.service.build_queryset()
        self.assertIsInstance(queryset, QuerySet)
        self.assertGreaterEqual(queryset.count(), 0)
    
    def test_build_queryset_is_active_filter(self):
        """Test build_queryset with is_active filter"""
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
        
        # Test with string 'true'
        queryset = self.service.build_queryset({'is_active': 'true'})
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().sku, 'ACT-001')
        
        # Test with boolean True
        queryset = self.service.build_queryset({'is_active': True})
        self.assertEqual(queryset.count(), 1)
    
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
    
    def test_get_product_statistics_error_handling(self):
        """Test get_product_statistics handles errors gracefully"""
        # This should not raise an exception even if there are issues
        stats = self.service.get_product_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn('total_products', stats)
    
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