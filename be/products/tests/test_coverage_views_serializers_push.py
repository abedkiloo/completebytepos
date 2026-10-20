"""Push products coverage past remaining serializer/view edges."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import UserProfile
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from products.models import Category, Color, Product, ProductVariant, Size
from products.serializers import (
    CategoryListSerializer,
    CategorySerializer,
    ProductSerializer,
)
from products.views import CategoryViewSet, ColorViewSet, ProductVariantViewSet
from settings.models import ModuleSetting
from settings.test_utils import disable_maker_checker, enable_maker_checker


def _seed():
    cache.clear()
    for key, default in (
        ('show_status', True),
        ('show_cost_price', True),
        ('show_mrp', True),
        ('show_sku_in_list', True),
        ('show_low_stock_badges', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='products',
            key=key,
            defaults={'label': key, 'description': '', 'default_value': default, 'value': default},
        )


class SerializerEdgePushTests(TestCase):
    def setUp(self):
        disable_maker_checker()
        _seed()
        self.parent = Category.objects.create(name='Push Parent', is_active=True)
        self.child = Category.objects.create(name='Push Child', parent=self.parent, is_active=True)
        self.product = Product.objects.create(
            name='Push Prod', sku='PUSH-1', barcode='BC-PUSH',
            category=self.parent, price=Decimal('20'), cost=Decimal('8'), is_active=True,
        )

    def test_sku_barcode_stock_layers_and_category_list(self):
        ser = ProductSerializer()
        ser.instance = self.product
        self.assertEqual(ser.validate_sku('PUSH-1'), 'PUSH-1')
        self.assertEqual(ser.validate_sku('PUSH-FREE'), 'PUSH-FREE')
        Product.objects.create(name='Other', sku='PUSH-DUP', price=Decimal('1'), is_active=True)
        with self.assertRaises(Exception):
            ProductSerializer().validate_sku('PUSH-DUP')

        self.assertEqual(ser.validate_barcode('BC-PUSH'), 'BC-PUSH')
        self.assertEqual(ser.validate_barcode(''), '')
        Product.objects.create(
            name='Other2', sku='PUSH-2', barcode='BC-TAKEN', price=Decimal('1'), is_active=True,
        )
        with self.assertRaises(Exception):
            ProductSerializer().validate_barcode('BC-TAKEN')

        with patch('inventory.stock_layers.layers_enabled', return_value=False):
            self.assertEqual(ProductSerializer().get_stock_layers(self.product), [])
        with patch('inventory.stock_layers.layers_enabled', return_value=True):
            layers = ProductSerializer().get_stock_layers(self.product)
            self.assertIsInstance(layers, list)

        data = CategoryListSerializer(self.parent).data
        self.assertIn('product_count', data)
        data2 = CategorySerializer(self.child).data
        self.assertIn('can_move_parent', data2)

        # validate subcategory mismatch after auto-populate fails
        other = Category.objects.create(name='Other Top Push', is_active=True)
        orphan = Category.objects.create(name='Orphan Sub', parent=other, is_active=True)
        bad = ProductSerializer(data={
            'name': 'Mismatch',
            'price': '10.00',
            'cost': '1.00',
            'category': self.parent.id,
            'subcategory': orphan.id,
        })
        # Autopopulate may rewrite category to orphan.parent — assert either invalid or rewritten
        if bad.is_valid():
            cat = bad.validated_data['category']
            self.assertEqual(getattr(cat, 'id', cat), other.id)
        else:
            self.assertTrue(bad.errors)

        # Nonexistent subcategory during validate
        ser3 = ProductSerializer()
        out = ser3.validate({
            'name': 'Ghost Sub',
            'price': Decimal('10'),
            'category': self.parent.id,
            'subcategory': 999999,
        })
        self.assertEqual(out.get('subcategory'), 999999)

    def test_create_update_supplier_object_paths(self):
        from suppliers.models import Supplier
        supplier = Supplier.objects.create(name='Push Sup', email='p@t.com', phone='3')
        ser = ProductSerializer()
        product = ser.create({
            'name': 'With Sup Obj',
            'sku': 'PUSH-SUP',
            'price': Decimal('12'),
            'supplier': supplier,
            'category': self.parent,
        })
        self.assertEqual(product.supplier_id, supplier.id)

        # Update with Supplier instance and with hasattr id object
        class IdOnly:
            def __init__(self, pk):
                self.id = pk

        updated = ser.update(product, {'supplier': IdOnly(supplier.id)})
        self.assertEqual(updated.supplier_id, supplier.id)
        updated = ser.update(updated, {'supplier': float(supplier.id)})
        self.assertEqual(updated.supplier_id, supplier.id)
        updated = ser.update(updated, {'subcategory': self.child})
        self.assertEqual(updated.subcategory_id, self.child.id)

        with patch.object(Product, 'save', side_effect=RuntimeError('boom save')):
            with self.assertRaises(RuntimeError):
                ser.update(updated, {'name': 'X'})


class CategoryColorVariantViewPushTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.manager = User.objects.create_user('push_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )

    def setUp(self):
        disable_maker_checker()
        _seed()
        self.factory = APIRequestFactory()
        self.parent = Category.objects.create(name='View Push Cat', is_active=True)
        self.color = Color.objects.create(name='View Push Color', is_active=True)
        self.product = Product.objects.create(
            name='Var Push', sku='VP-1', price=Decimal('10'), cost=Decimal('4'),
            has_variants=True, track_stock=True, is_active=True,
        )
        self.size = Size.objects.create(name='VP-S', code='VPS', is_active=True)
        self.variant = ProductVariant.objects.create(
            product=self.product, size=self.size, color=self.color,
            sku='VP-1-S', price=Decimal('10'), cost=Decimal('4'),
            stock_quantity=2, is_active=True,
        )

    def tearDown(self):
        disable_maker_checker()
        super().tearDown()

    def test_category_products_and_maker_checker_queues(self):
        disable_maker_checker()
        products_action = CategoryViewSet.as_view({'get': 'products'})
        req5 = self.factory.get(f'/api/products/categories/{self.parent.id}/products/')
        force_authenticate(req5, user=self.manager)
        self.assertEqual(products_action(req5, pk=self.parent.pk).status_code, status.HTTP_200_OK)

        view = CategoryViewSet.as_view({'patch': 'partial_update'})
        req = self.factory.patch(
            f'/api/products/categories/{self.parent.id}/',
            {'description': 'updated'},
            format='json',
        )
        force_authenticate(req, user=self.manager)
        self.assertEqual(view(req, pk=self.parent.pk).status_code, status.HTTP_200_OK)

        pending = MagicMock(id=1)
        enable_maker_checker()
        try:
            with patch(
                'approvals.category_integration.queue_category_deactivate',
                return_value=pending,
            ):
                with patch(
                    'approvals.serializers.PendingChangeSerializer',
                    return_value=MagicMock(data={'id': 1}),
                ):
                    req_mc = self.factory.patch(
                        f'/api/products/categories/{self.parent.id}/',
                        {'is_active': False},
                        format='json',
                    )
                    force_authenticate(req_mc, user=self.manager)
                    resp_mc = view(req_mc, pk=self.parent.pk)
            self.assertEqual(resp_mc.status_code, status.HTTP_202_ACCEPTED)

            with patch(
                'approvals.category_integration.queue_category_deactivate',
                side_effect=ValidationError({'reason': 'need reason'}),
            ):
                req_err = self.factory.patch(
                    f'/api/products/categories/{self.parent.id}/',
                    {'is_active': False},
                    format='json',
                )
                force_authenticate(req_err, user=self.manager)
                self.assertEqual(view(req_err, pk=self.parent.pk).status_code, status.HTTP_400_BAD_REQUEST)

            destroy = CategoryViewSet.as_view({'delete': 'destroy'})
            with patch(
                'approvals.category_integration.queue_category_delete',
                return_value=pending,
            ):
                with patch(
                    'approvals.serializers.PendingChangeSerializer',
                    return_value=MagicMock(data={'id': 1}),
                ):
                    req_d = self.factory.delete(f'/api/products/categories/{self.parent.id}/')
                    force_authenticate(req_d, user=self.manager)
                    self.assertEqual(destroy(req_d, pk=self.parent.pk).status_code, status.HTTP_202_ACCEPTED)

            with patch(
                'approvals.category_integration.queue_category_delete',
                side_effect=ValidationError('blocked'),
            ):
                req_db = self.factory.delete(f'/api/products/categories/{self.parent.id}/')
                force_authenticate(req_db, user=self.manager)
                self.assertEqual(destroy(req_db, pk=self.parent.pk).status_code, status.HTTP_400_BAD_REQUEST)
        finally:
            disable_maker_checker()

    def test_color_queryset_and_variant_maker_checker(self):
        disable_maker_checker()
        color_list = ColorViewSet.as_view({'get': 'list'})
        req = self.factory.get('/api/products/colors/?is_active=true')
        force_authenticate(req, user=self.manager)
        self.assertEqual(color_list(req).status_code, status.HTTP_200_OK)

        list_v = ProductVariantViewSet.as_view({'get': 'list'})
        req6 = self.factory.get(
            f'/api/products/variants/?product={self.product.id}&is_active=true'
        )
        force_authenticate(req6, user=self.manager)
        self.assertEqual(list_v(req6).status_code, status.HTTP_200_OK)

        update = ProductVariantViewSet.as_view({'patch': 'partial_update'})
        req7 = self.factory.patch(
            f'/api/products/variants/{self.variant.id}/',
            {'stock_quantity': 3},
            format='json',
        )
        force_authenticate(req7, user=self.manager)
        resp7 = update(req7, pk=self.variant.pk)
        self.assertEqual(resp7.status_code, status.HTTP_200_OK, getattr(resp7, 'data', None))

        pending = MagicMock(id=9)
        enable_maker_checker()
        try:
            destroy = ProductVariantViewSet.as_view({'delete': 'destroy'})
            with patch(
                'approvals.variant_integration.queue_variant_delete',
                return_value=pending,
            ):
                with patch(
                    'approvals.serializers.PendingChangeSerializer',
                    return_value=MagicMock(data={'id': 9}),
                ):
                    req2 = self.factory.delete(f'/api/products/variants/{self.variant.id}/')
                    force_authenticate(req2, user=self.manager)
                    self.assertEqual(destroy(req2, pk=self.variant.pk).status_code, status.HTTP_202_ACCEPTED)

            with patch(
                'approvals.variant_integration.queue_variant_delete',
                side_effect=ValidationError({'reason': 'x'}),
            ):
                req3 = self.factory.delete(f'/api/products/variants/{self.variant.id}/')
                force_authenticate(req3, user=self.manager)
                self.assertEqual(destroy(req3, pk=self.variant.pk).status_code, status.HTTP_400_BAD_REQUEST)

            with patch(
                'approvals.variant_integration.queue_variant_sensitive_update',
                side_effect=ValidationError({'reason': 'need reason'}),
            ):
                req4 = self.factory.patch(
                    f'/api/products/variants/{self.variant.id}/',
                    {'price': '12.00'},
                    format='json',
                )
                force_authenticate(req4, user=self.manager)
                self.assertEqual(update(req4, pk=self.variant.pk).status_code, status.HTTP_400_BAD_REQUEST)

            with patch(
                'approvals.variant_integration.queue_variant_sensitive_update',
                return_value=None,
            ):
                req5 = self.factory.patch(
                    f'/api/products/variants/{self.variant.id}/',
                    {'price': '13.00'},
                    format='json',
                )
                force_authenticate(req5, user=self.manager)
                # Maker-checker on + sensitive change + no pending → reason required
                self.assertEqual(update(req5, pk=self.variant.pk).status_code, status.HTTP_400_BAD_REQUEST)
        finally:
            disable_maker_checker()
