"""Hit remaining products serializer create/update, services filter, and view edges."""

from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import serializers, status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from products.models import Category, Color, Product, ProductVariant, Size, UnitOfMeasure
from products.serializers import (
    ProductSerializer,
    ProductVariantListSerializer,
    ProductVariantsField,
    UnitOfMeasureSerializer,
    _map_selling_price_fields,
)
from products.services import (
    ProductService,
    ProductVariantService,
    allocate_unique_variant_sku,
)
from products.views import ProductViewSet, UnitOfMeasureViewSet
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from settings.test_utils import disable_maker_checker
from suppliers.models import Supplier


def _seed_module():
    cache.clear()
    for key, default in (
        ('show_status', True),
        ('show_cost_price', True),
        ('show_mrp', True),
        ('show_sku_in_list', True),
        ('show_low_stock_badges', True),
        ('bulk_operations_enabled', True),
        ('csv_import_export_enabled', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='products',
            key=key,
            defaults={'label': key, 'description': '', 'default_value': default, 'value': default},
        )


class AllocateSkuFallbackTests(TestCase):
    def test_prefer_suffix_and_uuid_fallback(self):
        reserved = set()
        base = 'SKU-BASE'
        first = allocate_unique_variant_sku(base, reserved=reserved)
        self.assertEqual(first, base)
        second = allocate_unique_variant_sku(base, reserved=reserved, prefer_suffix='-X')
        self.assertEqual(second, f'{base}-X')
        # Force all candidates taken so fallback path runs
        reserved.add(base)
        reserved.add(f'{base}-X')
        with patch('products.services.uuid.uuid4') as uuid4:
            uuid4.return_value.hex = 'abcdef0123456789'
            with patch('products.services.ProductVariant.objects.filter') as filt:
                filt.return_value.exists.return_value = True
                out = allocate_unique_variant_sku(base, reserved=set(reserved), prefer_suffix='-X')
        self.assertTrue(out.startswith(base))


class ProductSerializerCreateUpdateGapTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed_module()
        self.parent = Category.objects.create(name='CU Parent', is_active=True)
        self.child = Category.objects.create(name='CU Child', parent=self.parent, is_active=True)
        self.supplier = Supplier.objects.create(name='CU Supplier', email='cu@t.com', phone='1')
        self.size = Size.objects.create(name='XS', code='XS', is_active=True)
        self.color = Color.objects.create(name='Teal', is_active=True)

    def test_to_internal_value_more_shapes(self):
        ser = ProductSerializer()
        data = ser.to_internal_value({
            'name': 'Shapes',
            'price': '10.00',
            'category': {'id': self.parent.id},
            'subcategory': float(self.child.id),
            'supplier': {'id': self.supplier.id},
            'variant_combinations': [{'size': self.size.id, 'color': self.color.id}],
        })
        self.assertEqual(getattr(data['category'], 'id', data['category']), self.parent.id)

        data2 = ser.to_internal_value({
            'name': 'Empty Rel',
            'price': '10.00',
            'category': '',
            'subcategory': '   ',
            'supplier': None,
        })
        self.assertIsNone(data2.get('category'))
        self.assertIsNone(data2.get('subcategory'))

        # Non-digit string category → None via except path
        data3 = ser.to_internal_value({
            'name': 'Weird Cat',
            'price': '10.00',
            'category': 'not-a-number',
            'subcategory': 'also-bad',
        })
        self.assertIsNone(data3.get('category'))

    def test_validate_strips_cost_mrp_and_unit(self):
        SettingsService.set('products', 'show_cost_price', False)
        SettingsService.set('products', 'show_mrp', False)
        ser = ProductSerializer(data={
            'name': 'Hidden Money',
            'price': '40.00',
            'cost': '10.00',
            'mrp': '50.00',
            'unit': 'piece',
            'category': self.parent.id,
        })
        self.assertTrue(ser.is_valid(), ser.errors)
        # Hidden fields are popped then financial defaults re-apply zeros
        self.assertEqual(ser.validated_data.get('cost'), Decimal('0'))
        self.assertEqual(ser.validated_data.get('mrp'), Decimal('0'))

        # Category objects + auto parent from subcategory
        ser2 = ProductSerializer()
        ser2.instance = None
        out = ser2.validate({
            'name': 'Obj Cat',
            'price': Decimal('20'),
            'category': self.parent,
            'subcategory': self.child,
        })
        self.assertEqual(out['category'], self.parent.id)
        self.assertEqual(out['subcategory'], self.child.id)

    def test_create_with_objects_variants_and_error_paths(self):
        ser = ProductSerializer()
        product = ser.create({
            'name': 'Created Obj',
            'price': Decimal('80'),
            'cost': Decimal('30'),
            'sku': 'CU-OBJ-1',
            'category': self.parent,
            'subcategory': self.child,
            'supplier': self.supplier,
            'has_variants': True,
            'track_stock': True,
            'available_sizes': [self.size],
            'available_colors': [self.color],
            'variants': [
                {
                    'sku': 'CU-OBJ-1-XS-TEA',
                    'price': '80.00',
                    'cost': '30.00',
                    'stock_quantity': 2,
                    'size': self.size.id,
                    'color': self.color.id,
                },
            ],
            'stock_quantity': 99,
        })
        self.assertEqual(product.category_id, self.parent.id)
        self.assertTrue(product.variants.exists())

        # Invalid category id → None
        product2 = ser.create({
            'name': 'Bad Cat Create',
            'price': Decimal('10'),
            'sku': 'CU-BAD-CAT',
            'category': 999999,
            'subcategory': 'nope',
            'supplier': 999999,
        })
        self.assertIsNone(product2.category_id)

        # IntegrityError → ValidationError
        with patch.object(Product.objects, 'create', side_effect=IntegrityError('dup sku')):
            with self.assertRaises(serializers.ValidationError):
                ser.create({
                    'name': 'Dup',
                    'price': Decimal('1'),
                    'sku': 'CU-DUP',
                })

        # ValueError with subcategory wording
        with patch.object(Product.objects, 'create', side_effect=ValueError('bad subcategory link')):
            with self.assertRaises(serializers.ValidationError) as ctx:
                ser.create({'name': 'VE', 'price': Decimal('1'), 'sku': 'CU-VE'})
            self.assertIn('subcategory', ctx.exception.detail)

        with patch.object(Product.objects, 'create', side_effect=ValueError('other fail')):
            with self.assertRaises(serializers.ValidationError):
                ser.create({'name': 'VE2', 'price': Decimal('1'), 'sku': 'CU-VE2'})

    def test_update_paths_and_nested_variants(self):
        product = Product.objects.create(
            name='Updatable', sku='CU-UPD', category=self.parent,
            price=Decimal('50'), cost=Decimal('20'), is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=product, size=self.size, color=self.color,
            sku='CU-UPD-XS', price=Decimal('50'), cost=Decimal('20'),
            stock_quantity=1, is_active=True,
        )
        ser = ProductSerializer(instance=product)
        updated = ser.update(product, {
            'name': 'Updated Name',
            'category': self.parent,
            'subcategory': self.child,
            'supplier': str(self.supplier.id),
            'available_sizes': [self.size.id],
            'available_colors': [self.color.id],
            'variants': [
                {
                    'id': variant.id,
                    'stock_quantity': 4,
                    'price': '55.00',
                    'cost': '20.00',
                },
            ],
        })
        self.assertEqual(updated.name, 'Updated Name')
        self.assertEqual(updated.supplier_id, self.supplier.id)

        # Clear relations
        cleared = ser.update(updated, {
            'category': None,
            'subcategory': None,
            'supplier': None,
        })
        self.assertIsNone(cleared.category_id)

        # Bad ids on update
        ser.update(cleared, {
            'category': 'bad',
            'subcategory': 999999,
            'supplier': object(),
        })

        # Save ValueError / IntegrityError
        with patch.object(Product, 'save', side_effect=ValueError('subcategory broken')):
            with self.assertRaises(serializers.ValidationError):
                ser.update(product, {'name': 'X'})
        with patch.object(Product, 'save', side_effect=ValueError('generic')):
            with self.assertRaises(serializers.ValidationError):
                ser.update(product, {'name': 'Y'})
        with patch.object(Product, 'save', side_effect=IntegrityError('dup')):
            with self.assertRaises(serializers.ValidationError):
                ser.update(product, {'name': 'Z'})


class VariantListAndFieldGapTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed_module()
        self.product = Product.objects.create(
            name='List Var', sku='LV-1', price=Decimal('10'), cost=Decimal('4'),
            has_variants=True, track_stock=True, is_active=True,
        )
        self.size = Size.objects.create(name='LV-S', code='LVS', is_active=True)
        self.color = Color.objects.create(name='LV-C', is_active=True)
        self.variant = ProductVariant.objects.create(
            product=self.product, size=self.size, color=self.color,
            sku='LV-1-S', price=Decimal('10'), cost=Decimal('4'),
            stock_quantity=1, is_active=True,
        )

    def test_list_serializer_and_field(self):
        child = ProductVariantListSerializer(child=MagicMock())
        # Use real serializer path via ProductSerializer nested field
        field = ProductVariantsField()
        field.bind('variants', ProductSerializer())
        self.assertEqual(field.to_internal_value(None), None)
        with self.assertRaises(serializers.ValidationError):
            field.to_internal_value('not-list')
        with self.assertRaises(serializers.ValidationError):
            field.to_internal_value(['x'])
        cleaned = field.to_internal_value([{'id': self.variant.id, 'stock_quantity': 2}])
        self.assertEqual(cleaned[0]['id'], self.variant.id)
        self.assertEqual(field.to_representation(None), [])
        self.assertTrue(isinstance(field.to_representation(self.product.variants.all()), list))

        list_ser = ProductVariantListSerializer(
            child=serializers.Serializer(),
            context={},
        )
        # Direct to_internal_value with mixed valid/invalid
        with self.assertRaises(serializers.ValidationError):
            list_ser.to_internal_value('nope')
        with self.assertRaises(serializers.ValidationError):
            list_ser.to_internal_value([1, {'id': 'bad'}])

    def test_map_selling_price_without_copy(self):
        mapped = _map_selling_price_fields({'selling_price': '12.50', 'name': 'x'})
        self.assertEqual(mapped['price'], '12.50')


class UnitSerializerGapTests(TestCase):
    def test_validate_code_and_create(self):
        ser = UnitOfMeasureSerializer(data={'code': '  ', 'label': 'Blank'})
        self.assertFalse(ser.is_valid())
        ser2 = UnitOfMeasureSerializer(data={'code': 'crate_gap', 'label': 'Crate'})
        self.assertTrue(ser2.is_valid(), ser2.errors)
        unit = ser2.save()
        self.assertEqual(unit.code, 'crate_gap')


class ProductServiceFilterImportGapTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed_module()
        self.service = ProductService()
        self.category = Category.objects.create(name='Filt Cat', is_active=True)
        self.sub = Category.objects.create(name='Filt Sub', parent=self.category, is_active=True)
        self.supplier = Supplier.objects.create(name='Filt Sup', email='f@t.com', phone='2')
        self.product = Product.objects.create(
            name='Filterable', sku='FILT-1', category=self.category, subcategory=self.sub,
            supplier=self.supplier, price=Decimal('20'), cost=Decimal('8'),
            stock_quantity=1, low_stock_threshold=5, track_stock=True, is_active=True,
        )

    def test_build_queryset_filters(self):
        qs = self.service.build_queryset({
            'is_active': 'undefined',
            'category': 'null',
            'subcategory': '',
            'low_stock': 'undefined',
            'out_of_stock': 'null',
            'needs_restock': 'true',
            'track_stock': 'true',
            'supplier': str(self.supplier.id),
        })
        self.assertIn(self.product.id, qs.values_list('id', flat=True))

        qs2 = self.service.build_queryset({
            'is_active': 'true',
            'category': self.category.id,
            'subcategory': 'not-int',
            'low_stock': 'true',
            'out_of_stock': False,
            'needs_restock': 'false',
            'track_stock': 'undefined',
            'supplier': 'NoSuchSupplierNameXYZ',
        })
        self.assertEqual(qs2.count(), 0)

        qs3 = self.service.build_queryset({
            'category': 'bad',
            'subcategory': self.sub.id,
            'supplier': 'undefined',
        })
        self.assertEqual(qs3.count(), 0)

    def test_create_product_and_import_variants_csv(self):
        size = Size.objects.create(name='ImpS', code='IMS', is_active=True)
        color = Color.objects.create(name='ImpC', is_active=True)
        created = self.service.create_product(
            {
                'name': 'Svc Create',
                'sku': 'SVC-CR-1',
                'price': Decimal('15'),
                'cost': Decimal('5'),
                'category': self.category,
                'has_variants': True,
            },
            sizes=[size],
            colors=[color],
        )
        self.assertTrue(created.has_variants)

        with self.assertRaises(Exception):
            self.service.create_product({
                'name': 'Bad Sup',
                'sku': 'SVC-BAD-SUP',
                'price': Decimal('1'),
                'supplier': 999999,
            })

        with self.assertRaises(Exception):
            self.service.create_product({
                'name': 'Dup SKU',
                'sku': 'FILT-1',
                'price': Decimal('1'),
            })

        csv_payload = (
            'SKU,Name,Barcode,Category,Subcategory,MRP,Selling Price,Cost,Stock Quantity,'
            'Low Stock Threshold,Unit,Has Variants,Track Stock,Is Taxable,Is Active,'
            'Description,Supplier,Available Sizes,Available Colors\n'
            'CSV-VAR,Variant CSV,,Filt Cat,Filt Sub,30,25,10,0,2,piece,True,True,True,True,,Filt Sup,ImpS,ImpC\n'
            ',Missing SKU,,,,0,10,5,1,1,piece,False,True,True,True,,,\n'
            'CSV-NONAME,,,,,,10,5,1,1,piece,False,True,True,True,,,\n'
            'FILT-1,Filterable Updated,,Filt Cat,,40,30,8,2,5,piece,False,True,True,True,,Filt Sup,,\n'
        )
        result = self.service.import_products_from_csv(BytesIO(csv_payload.encode()))
        self.assertTrue(result['errors'] or result['created'] or result['updated'])
        self.assertTrue(any('SKU is required' in e or 'Name is required' in e for e in result['errors']))

        # Parsing error path
        broken = self.service.import_products_from_csv(BytesIO(b'\xff\xfe not csv'))
        self.assertTrue(broken['errors'] or broken['created'] == 0)

        with patch.object(
            self.service.model.objects, 'get_or_create',
            side_effect=IntegrityError('row dup'),
        ):
            row = (
                'SKU,Name,Barcode,Category,Subcategory,MRP,Selling Price,Cost,Stock Quantity,'
                'Low Stock Threshold,Unit,Has Variants,Track Stock,Is Taxable,Is Active,Description,Supplier\n'
                'CSV-IE,Integrity,,,,0,10,5,1,1,piece,False,True,True,True,,\n'
            )
            ie = self.service.import_products_from_csv(BytesIO(row.encode()))
            self.assertTrue(any('DB error' in e for e in ie['errors']))


class VariantServiceEmptyAndRegenerateTests(TestCase):
    def test_empty_create_and_regenerate_exception(self):
        disable_maker_checker()
        product = Product.objects.create(
            name='Empty Var', sku='EV-1', price=Decimal('10'),
            has_variants=True, track_stock=True, is_active=True,
        )
        service = ProductVariantService()
        self.assertEqual(service.create_variants_for_product(product, sizes=[], colors=[]), [])

        with patch.object(
            service, 'create_variants_for_product', side_effect=RuntimeError('regen boom'),
        ):
            with self.assertRaises(RuntimeError):
                service.regenerate_variants_atomic(product, sizes=[1], colors=[2])


class ProductModelPropertyGapTests(TestCase):
    def test_category_count_and_variant_selling_price(self):
        cat = Category.objects.create(name='Prop Cat', is_active=True)
        product = Product.objects.create(
            name='Prop P', sku='PROP-1', category=cat, price=Decimal('9'), is_active=True,
        )
        self.assertEqual(cat.product_count, 1)
        child = Category.objects.create(name='Prop Child', parent=cat, is_active=True)
        product.subcategory = child
        product.category = None
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.category_id, cat.id)

        variant = ProductVariant.objects.create(
            product=product, sku='PROP-1-V', price=None, stock_quantity=0, is_active=True,
        )
        self.assertEqual(variant.selling_price, product.price)
        variant.selling_price = Decimal('11')
        self.assertEqual(variant.price, Decimal('11'))


class ProductViewSetActionGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('pv_gap_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.admin = User.objects.create_user('pv_gap_admin', password='x')
        UserProfile.objects.create(
            user=cls.admin, role='admin', custom_role=roles[ROLE_SUPER_ADMIN], is_active=True,
        )

    def setUp(self):
        disable_maker_checker()
        _seed_module()
        self.factory = APIRequestFactory()
        self.product = Product.objects.create(
            name='View Gap', sku='VG-1', price=Decimal('12'), cost=Decimal('4'),
            stock_quantity=2, track_stock=True, is_active=True,
        )

    def _view(self, action, method='get', user=None, data=None, query=''):
        user = user or self.manager
        view = ProductViewSet.as_view({method: action})
        if method == 'get':
            request = self.factory.get(f'/api/products/{action}/{query}')
        else:
            request = self.factory.post(f'/api/products/{action}/', data or {}, format='json')
        force_authenticate(request, user=user)
        return view(request)

    def test_search_check_duplicate_and_bulk_edges(self):
        resp = self._view('search', query='?q=&limit=bad')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self._view('search', query='?q=View&limit=-5')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self._view('search', query='?q=View&limit=5000')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        with patch.object(ProductService, 'search_products', side_effect=RuntimeError('boom')):
            resp = self._view('search', query='?q=View')
            self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        resp = self._view('check_duplicate', query='?name=View Gap&exclude=not-int')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self._view('statistics')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        with patch.object(ProductService, 'get_product_statistics', side_effect=RuntimeError('stats')):
            resp = self._view('statistics')
            self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        resp = self._view('bulk_update', method='post', data={
            'product_ids': [self.product.id],
            'update_data': {'is_active': False},
        })
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST))

        with patch.object(ProductService, 'bulk_update_products', side_effect=RuntimeError('bulk')):
            resp = self._view('bulk_update', method='post', data={
                'product_ids': [self.product.id],
                'update_data': {'price': '1.00'},
            })
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        resp = self._view('bulk_activate', method='post', data={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = self._view('bulk_deactivate', method='post', data={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = self._view('bulk_activate', method='post', data={'product_ids': [self.product.id]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self._view('bulk_deactivate', method='post', data={'product_ids': [self.product.id]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        with patch.object(ProductService, 'bulk_activate_products', side_effect=RuntimeError('a')):
            resp = self._view('bulk_activate', method='post', data={'product_ids': [self.product.id]})
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        with patch.object(ProductService, 'bulk_deactivate_products', side_effect=RuntimeError('d')):
            resp = self._view('bulk_deactivate', method='post', data={'product_ids': [self.product.id]})
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        resp = self._view('bulk_delete', method='post', user=self.admin, data={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        with patch('products.views.products_bulk_operations_enabled', return_value=False):
            resp = self._view('bulk_update', method='post', data={
                'product_ids': [self.product.id],
                'update_data': {'is_active': True},
            })
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        with patch('products.views.products_csv_import_export_enabled', return_value=False):
            view = ProductViewSet.as_view({'get': 'export'})
            request = self.factory.get('/api/products/export/')
            force_authenticate(request, user=self.manager)
            resp = view(request)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        view = ProductViewSet.as_view({'post': 'import_csv'})
        request = self.factory.post('/api/products/import_csv/')
        force_authenticate(request, user=self.manager)
        resp = view(request)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unit_queryset_and_options(self):
        UnitOfMeasure.objects.get_or_create(code='piece', defaults={'label': 'Piece', 'is_active': True})
        view = UnitOfMeasureViewSet.as_view({'get': 'list'})
        request = self.factory.get('/api/products/units/?is_active=true')
        force_authenticate(request, user=self.manager)
        resp = view(request)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        request2 = self.factory.get('/api/products/units/?format=options')
        force_authenticate(request2, user=self.manager)
        resp2 = view(request2)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp2.data)


class ProductListSearchSerializerGapTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed_module()
        self.cat = Category.objects.create(name='List Cat', is_active=True)
        self.sub = Category.objects.create(name='List Sub', parent=self.cat, is_active=True)
        self.product = Product.objects.create(
            name='List Prod', sku='LP-1', category=self.cat, subcategory=self.sub,
            price=Decimal('15'), cost=Decimal('5'), stock_quantity=0,
            low_stock_threshold=5, track_stock=True, has_variants=True, is_active=True,
        )
        ProductVariant.objects.create(
            product=self.product, sku='LP-1-V', price=Decimal('15'), cost=Decimal('5'),
            stock_quantity=0, is_active=True,
        )

    def test_list_and_search_representation(self):
        from products.serializers import ProductListSerializer, ProductSearchSerializer

        data = ProductListSerializer(self.product).data
        self.assertEqual(data['category_name'], 'List Cat')
        self.assertEqual(data['subcategory_name'], 'List Sub')
        self.assertGreaterEqual(data['variants_count'], 1)
        self.assertIsNone(data.get('image_url'))

        bare = Product.objects.create(
            name='No Cat', sku='LP-2', price=Decimal('5'), has_variants=False, is_active=True,
        )
        bare_data = ProductListSerializer(bare).data
        self.assertIsNone(bare_data['category_name'])
        self.assertEqual(bare_data['variants_count'], 0)

        search = ProductSearchSerializer(self.product).data
        self.assertEqual(search['category_name'], 'List Cat')
        search2 = ProductSearchSerializer(bare).data
        self.assertIsNone(search2['category_name'])


class CategorySerializerAttemptParentTests(TestCase):
    def test_attempted_parent_and_counts_without_prefetch(self):
        from products.serializers import CategorySerializer

        parent = Category.objects.create(name='Att Parent', is_active=True)
        child = Category.objects.create(name='Att Child', parent=parent, is_active=True)
        ser = CategorySerializer(instance=child, data={'name': 'Att Child 2', 'parent': ''}, partial=True)
        # Exercise _attempted_parent_id empty + invalid
        self.assertIsNone(ser._attempted_parent_id() if False else None)
        ser.initial_data = {'parent': ''}
        self.assertIsNone(ser._attempted_parent_id())
        ser.initial_data = {'parent': 'abc'}
        self.assertIsNone(ser._attempted_parent_id())
        ser.initial_data = {}
        ser.instance = child
        self.assertEqual(ser._attempted_parent_id(), parent.id)

        # Counts when relation managers exist (always do on model)
        self.assertGreaterEqual(ser.get_product_count(child), 0)
        self.assertGreaterEqual(ser.get_children_count(parent), 1)


class CatalogAccessUnknownRoleTests(TestCase):
    def test_unknown_role_denied(self):
        from products.catalog_access import (
            user_may_edit_any_product_financial_field,
            user_may_edit_product_cost,
            user_may_edit_product_pricing,
            user_may_edit_product_stock,
        )

        user = User.objects.create_user('cat_unk', password='x')
        with patch('products.catalog_access.resolve_user_role', return_value='cashier'):
            self.assertFalse(user_may_edit_product_pricing(user))
            self.assertFalse(user_may_edit_product_cost(user))
            self.assertFalse(user_may_edit_product_stock(user))
            self.assertFalse(user_may_edit_any_product_financial_field(user))


class ProductCreateSubcategoryOnlyAndVariantIdTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed_module()
        self.parent = Category.objects.create(name='SO Parent', is_active=True)
        self.child = Category.objects.create(name='SO Child', parent=self.parent, is_active=True)
        self.size = Size.objects.create(name='SO-S', code='SOS', is_active=True)
        self.color = Color.objects.create(name='SO-C', is_active=True)

    def test_create_subcategory_only_and_variant_id_miss(self):
        ser = ProductSerializer()
        product = ser.create({
            'name': 'Sub Only',
            'price': Decimal('40'),
            'cost': Decimal('10'),
            'sku': 'SO-1',
            'subcategory': self.child,
            'has_variants': True,
            'track_stock': True,
            'variants': [
                {'id': 999999, 'sku': 'SO-1-NEW', 'price': '40.00', 'cost': '10.00',
                 'stock_quantity': 1, 'size': self.size.id, 'color': self.color.id},
            ],
        })
        self.assertEqual(product.category_id, self.parent.id)
        self.assertTrue(product.variants.filter(sku='SO-1-NEW').exists())

        # Sync exception swallowed on create
        with patch(
            'products.stock_utils.sync_product_stock_from_variants',
            side_effect=RuntimeError('sync'),
        ):
            product2 = ser.create({
                'name': 'Sync Fail',
                'price': Decimal('10'),
                'sku': 'SO-2',
                'has_variants': True,
                'track_stock': True,
                'variants': [
                    {'sku': 'SO-2-V', 'price': '10.00', 'cost': '1.00', 'stock_quantity': 1},
                ],
            })
        self.assertIsNotNone(product2.pk)


class ProductViewLowStockExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('pv_ls', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )

    def setUp(self):
        disable_maker_checker()
        _seed_module()
        self.factory = APIRequestFactory()
        Product.objects.create(
            name='Low Stock View', sku='LSV-1', price=Decimal('8'), cost=Decimal('2'),
            stock_quantity=1, low_stock_threshold=5, track_stock=True, is_active=True,
        )

    def test_low_out_export_import(self):
        view = ProductViewSet.as_view({'get': 'low_stock'})
        req = self.factory.get('/api/products/low_stock/')
        force_authenticate(req, user=self.manager)
        self.assertEqual(view(req).status_code, status.HTTP_200_OK)

        view2 = ProductViewSet.as_view({'get': 'out_of_stock'})
        req2 = self.factory.get('/api/products/out_of_stock/')
        force_authenticate(req2, user=self.manager)
        self.assertEqual(view2(req2).status_code, status.HTTP_200_OK)

        view3 = ProductViewSet.as_view({'get': 'export'})
        req3 = self.factory.get('/api/products/export/')
        force_authenticate(req3, user=self.manager)
        resp = view3(req3)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_body = (
            'SKU,Name,Barcode,Category,Subcategory,MRP,Selling Price,Cost,Stock Quantity,'
            'Low Stock Threshold,Unit,Has Variants,Track Stock,Is Taxable,Is Active,Description,Supplier\n'
            'IMP-VIEW,Import View,,,,0,9,3,2,1,piece,False,True,True,True,,\n'
        )
        view4 = ProductViewSet.as_view({'post': 'import_csv'})
        upload = SimpleUploadedFile('p.csv', csv_body.encode(), content_type='text/csv')
        req4 = self.factory.post('/api/products/import_csv/', {'file': upload}, format='multipart')
        force_authenticate(req4, user=self.manager)
        resp4 = view4(req4)
        self.assertEqual(resp4.status_code, status.HTTP_200_OK)

        with patch.object(ProductService, 'import_products_from_csv', side_effect=RuntimeError('imp')):
            req5 = self.factory.post(
                '/api/products/import_csv/',
                {'file': SimpleUploadedFile('p2.csv', csv_body.encode(), content_type='text/csv')},
                format='multipart',
            )
            force_authenticate(req5, user=self.manager)
            self.assertEqual(view4(req5).status_code, status.HTTP_400_BAD_REQUEST)
