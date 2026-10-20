"""Focused unit coverage for products helpers with remaining gaps."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import serializers

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SALES, ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from products.catalog_access import user_may_edit_catalog_details
from products.category_validation import (
    DuplicateCategoryInfo,
    find_duplicate_category,
    normalize_category_name,
)
from products.duplicates import find_duplicate_product, normalize_product_name
from products.models import Category, Color, Product, ProductVariant, Size, UnitOfMeasure
from products.module_settings import (
    apply_product_list_representation_flags,
    products_allow_sales_catalog_access,
)
from products.serializers import (
    ProductSerializer,
    ProductVariantListSerializer,
    ProductVariantsField,
    UnitOfMeasureSerializer,
    _apply_product_financial_defaults,
    _coerce_boolish,
    _map_selling_price_fields,
    _price_cost_validation_errors,
    _validate_nested_variant_writes,
)
from products.services import CategoryService, ProductVariantService, allocate_unique_variant_sku
from products.status_rules import strip_product_status_filter
from products.stock_utils import (
    active_variant_stock_sum,
    sync_product_cost_from_variants,
)
from products.units import create_unit, validate_unit_code
from products.variant_combinations import (
    normalize_variant_combinations,
    sync_product_variant_combinations,
)
from settings.models import ModuleSetting
from settings.settings_service import SettingsService
from settings.test_utils import disable_maker_checker


def _seed_products_settings():
    cache.clear()
    for key, default in (
        ('show_status', True),
        ('show_cost_price', True),
        ('show_mrp', True),
        ('show_sku_in_list', False),
        ('show_low_stock_badges', True),
        ('allow_sales_catalog_access', True),
        ('allow_sales_edit_catalog_details', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='products',
            key=key,
            defaults={'label': key, 'description': '', 'default_value': default, 'value': default},
        )


class VariantCombinationsGapTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        self.category = Category.objects.create(name='VC Gap', is_active=True)
        self.size = Size.objects.create(name='S', code='S', is_active=True)
        self.color = Color.objects.create(name='Green', is_active=True)
        self.product = Product.objects.create(
            name='Gap Shirt', sku='GAP-SH', category=self.category,
            price=Decimal('80'), has_variants=True, track_stock=True, is_active=True,
        )

    def test_normalize_edges(self):
        self.assertEqual(normalize_variant_combinations(None), [])
        self.assertEqual(normalize_variant_combinations(''), [])
        self.assertEqual(normalize_variant_combinations({'size': 1}), [])
        self.assertEqual(
            normalize_variant_combinations([[self.size.id, self.color.id], 'skip', [None, None]]),
            [{'size': self.size.id, 'color': self.color.id}],
        )
        # Dedup + invalid ints
        raw = [
            {'size': 'bad', 'color': self.color.id},
            {'size': self.size.id, 'color': self.color.id},
            {'size': self.size.id, 'color': self.color.id},
            {'size_id': self.size.id, 'color_id': None},
        ]
        out = normalize_variant_combinations(raw)
        # bad size dropped color-only? size 'bad'→None keeps color; plus size+color; plus size-only
        self.assertEqual(len(out), 3)

    def test_sync_skips_when_no_variants_and_skips_existing(self):
        plain = Product.objects.create(
            name='Plain', sku='PLAIN-1', category=self.category,
            price=Decimal('10'), has_variants=False, is_active=True,
        )
        self.assertEqual(sync_product_variant_combinations(plain, [{'size': 1, 'color': 2}]), [])
        sync_product_variant_combinations(
            self.product, [{'size': self.size.id, 'color': self.color.id}],
        )
        created = sync_product_variant_combinations(
            self.product, [{'size': self.size.id, 'color': self.color.id}],
        )
        self.assertEqual(created, [])
        self.assertEqual(ProductVariant.objects.filter(product=self.product).count(), 1)


class ModuleSettingsGapTests(TestCase):
    def setUp(self):
        _seed_products_settings()

    def test_allow_sales_catalog_and_list_flags(self):
        self.assertTrue(products_allow_sales_catalog_access())
        SettingsService.set('products', 'show_cost_price', False)
        SettingsService.set('products', 'show_mrp', False)
        SettingsService.set('products', 'show_sku_in_list', False)
        SettingsService.set('products', 'show_low_stock_badges', False)
        SettingsService.set('products', 'show_status', False)
        data = apply_product_list_representation_flags({
            'is_active': True,
            'cost': '1',
            'mrp': '2',
            'sku': 'X',
            'is_low_stock': True,
        })
        self.assertNotIn('cost', data)
        self.assertNotIn('is_low_stock', data)


class UnitsGapTests(TestCase):
    def test_validate_and_create_unit_errors(self):
        with self.assertRaises(ValidationError):
            validate_unit_code('')
        with self.assertRaises(ValidationError):
            create_unit('', 'Label')
        with self.assertRaises(ValidationError):
            create_unit('custom', '')
        unit = create_unit('crate', 'Crate')
        self.assertEqual(unit.code, 'crate')
        ser = UnitOfMeasureSerializer(data={'code': '', 'label': 'X'})
        self.assertFalse(ser.is_valid())


class CategoryValidationGapTests(TestCase):
    def test_normalize_none_and_duplicate_messages(self):
        self.assertEqual(normalize_category_name(None), '')
        self.assertIsNone(find_duplicate_category(''))

        parent = Category.objects.create(name='Parent Gap', is_active=True)
        top = Category.objects.create(name='Dup Top', is_active=True)
        inactive = Category.objects.create(name='Inactive Cat', is_active=False)
        sub = Category.objects.create(name='Dup Sub', parent=parent, is_active=True)

        info = DuplicateCategoryInfo(inactive)
        self.assertIn('inactive', info.user_message('Inactive Cat'))

        info_sub = DuplicateCategoryInfo(sub)
        self.assertIn('subcategory', info_sub.user_message('Dup Sub', attempted_parent_id=parent.id))
        self.assertIn('already exists', info_sub.user_message('Dup Sub', attempted_parent_id=999))

        info_top = DuplicateCategoryInfo(top)
        self.assertIn('top-level', info_top.user_message('Dup Top', attempted_parent_id=parent.id))
        self.assertIn('Choose a different name', info_top.user_message('Dup Top'))


class StockUtilsGapTests(TestCase):
    def test_active_sum_and_cost_sync_update(self):
        product = Product.objects.create(
            name='Stock Gap', sku='SG-1', price=Decimal('100'), cost=Decimal('10'),
            has_variants=False, track_stock=True, is_active=True,
        )
        self.assertEqual(active_variant_stock_sum(product), 0)

        product.has_variants = True
        product.save(update_fields=['has_variants'])
        size = Size.objects.create(name='M', code='M', is_active=True)
        color = Color.objects.create(name='Blue', is_active=True)
        ProductVariant.objects.create(
            product=product, size=size, color=color, sku='SG-1-M-BLU',
            price=Decimal('100'), cost=Decimal('40'), stock_quantity=4, is_active=True,
        )
        avg = sync_product_cost_from_variants(product)
        self.assertEqual(avg, Decimal('40.00'))
        product.refresh_from_db()
        self.assertEqual(product.cost, Decimal('40.00'))


class CatalogAccessGapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.roles = roles

    def setUp(self):
        _seed_products_settings()

    def test_super_admin_manager_and_unknown_role(self):
        admin = User.objects.create_user('ca_admin', password='x')
        UserProfile.objects.create(
            user=admin, role='super_admin', custom_role=self.roles[ROLE_SUPER_ADMIN], is_active=True,
        )
        self.assertTrue(user_may_edit_catalog_details(admin))

        mgr = User.objects.create_user('ca_mgr', password='x')
        UserProfile.objects.create(
            user=mgr, role='manager', custom_role=self.roles[ROLE_MANAGER], is_active=True,
        )
        self.assertTrue(user_may_edit_catalog_details(mgr))

        bare = User.objects.create_user('ca_bare', password='x')
        self.assertFalse(user_may_edit_catalog_details(bare))


class DuplicatesAndStatusGapTests(TestCase):
    def setUp(self):
        _seed_products_settings()

    def test_empty_name_and_strip_status_none_filters(self):
        self.assertEqual(normalize_product_name(None), '')
        self.assertIsNone(find_duplicate_product(''))
        self.assertEqual(strip_product_status_filter(None), {})


class SerializerHelperGapTests(TestCase):
    def test_map_coerce_price_and_nested_variants(self):
        self.assertEqual(_map_selling_price_fields({'selling_price': '12'})['price'], '12')
        self.assertTrue(_coerce_boolish('yes'))
        self.assertFalse(_coerce_boolish('no'))
        self.assertTrue(_coerce_boolish(1))

        err = _price_cost_validation_errors({'cost'}, Decimal('5'), Decimal('10'))
        self.assertIn('cost', err)
        err2 = _price_cost_validation_errors({'price'}, Decimal('5'), Decimal('10'))
        self.assertIn('price', err2)

        create_defaults = _apply_product_financial_defaults({'price': None, 'mrp': None, 'cost': None})
        self.assertEqual(create_defaults['price'], Decimal('0'))
        product = Product.objects.create(name='Fin', sku='FIN-1', price=Decimal('9'), is_active=True)
        updated = _apply_product_financial_defaults(
            {'price': None, 'mrp': None}, instance=product,
        )
        self.assertNotIn('price', updated)

        self.assertIsNone(_validate_nested_variant_writes(None, {}))
        with self.assertRaises(serializers.ValidationError):
            _validate_nested_variant_writes('nope', {})
        with self.assertRaises(serializers.ValidationError):
            _validate_nested_variant_writes([1], {})
        cleaned = _validate_nested_variant_writes([{'sku': 'X'}], {})
        self.assertEqual(cleaned[0]['sku'], 'X')

        field = ProductVariantsField()
        self.assertEqual(field.to_representation(None), [])

    def test_variant_list_serializer_validation(self):
        from products.serializers import ProductVariantSerializer

        product = Product.objects.create(name='VL', sku='VL-1', price=Decimal('10'), is_active=True)
        variant = ProductVariant.objects.create(
            product=product, sku='VL-1-A', price=Decimal('10'), stock_quantity=1, is_active=True,
        )
        list_ser = ProductVariantListSerializer(child=ProductVariantSerializer())
        with self.assertRaises(serializers.ValidationError):
            list_ser.to_internal_value('not-a-list')
        with self.assertRaises(serializers.ValidationError):
            list_ser.to_internal_value(['not-dict'])
        out = list_ser.to_internal_value([
            {'id': variant.id, 'stock_quantity': 3},
            {
                'id': 999999,
                'product': product.id,
                'sku': 'NEW-V',
                'price': '10.00',
                'stock_quantity': 1,
            },
        ])
        self.assertEqual(len(out), 2)


class CategoryServiceGapTests(TestCase):
    def test_get_with_children_and_exact_name_none(self):
        parent = Category.objects.create(name='Svc Parent', is_active=True)
        Category.objects.create(name='Svc Child', parent=parent, is_active=True)
        svc = CategoryService()
        loaded = svc.get_category_with_children(parent.id)
        self.assertEqual(loaded.id, parent.id)
        qs = svc.build_queryset({'exact_name': '   '})
        self.assertEqual(qs.count(), 0)


class VariantSkuAllocationGapTests(TestCase):
    def test_allocate_unique_with_collision_and_create_variants(self):
        product = Product.objects.create(
            name='SKU Gap', sku='SKUG', price=Decimal('10'),
            has_variants=True, track_stock=True, is_active=True,
        )
        size = Size.objects.create(name='XL', code='XL', is_active=True)
        color = Color.objects.create(name='Pink', is_active=True)
        ProductVariant.objects.create(
            product=product, size=size, color=color, sku='SKUG-XL-PIN',
            price=Decimal('10'), stock_quantity=1, is_active=True,
        )
        reserved = {'SKUG-XL-PIN'}
        sku = allocate_unique_variant_sku('SKUG-XL-PIN', reserved=reserved, prefer_suffix='9')
        self.assertNotEqual(sku, 'SKUG-XL-PIN')
        self.assertIn(sku, reserved)

        service = ProductVariantService()
        product2 = Product.objects.create(
            name='SKU Gap 2', sku='SKUG2', price=Decimal('10'),
            has_variants=True, track_stock=True, is_active=True,
        )
        color3 = Color.objects.create(name='Amber', is_active=True)
        created = service.create_variants_for_product(
            product2, sizes=[size.id], colors=[color.id, color3.id],
        )
        self.assertEqual(len(created), 2)

        # Empty when product has no variants flag
        plain = Product.objects.create(
            name='NoVar', sku='NOVAR', price=Decimal('1'), has_variants=False, is_active=True,
        )
        self.assertEqual(service.create_variants_for_product(plain, sizes=[size.id]), [])

        # IntegrityError retry path on _create_variant
        color4 = Color.objects.create(name='Ivory', is_active=True)
        call_count = {'n': 0}
        real_create = ProductVariant.objects.create

        def flaky_create(**kwargs):
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise IntegrityError('dup sku')
            return real_create(**kwargs)

        with patch.object(ProductVariant.objects, 'create', side_effect=flaky_create):
            variant = service._create_variant(product2, size, color4)
        self.assertIsNotNone(variant.pk)
