"""Focused unit/API coverage for suppliers helpers and view edge paths."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from rest_framework import status

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ensure_permissions, sync_default_roles
from products.models import Product
from settings.models import ModuleSetting, ModuleSettings
from settings.settings_service import SettingsService
from suppliers.admin import SupplierAdmin
from suppliers.models import Supplier
from suppliers.module_settings import (
    apply_supplier_representation_flags,
    suppliers_enable_delete,
    suppliers_enable_edit,
    suppliers_enable_products,
    suppliers_enable_statistics,
    suppliers_show_supplier_code,
    validate_supplier_write,
)
from suppliers.serializers import SupplierSerializer
from suppliers.services import SupplierService
from suppliers.tests.test_module_settings_phase3 import _seed_supplier_settings
from suppliers.views import HasSupplierPermission, SupplierViewSet
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


def _seed_all_supplier_flags():
    _seed_supplier_settings()
    for key, default in (
        ('show_supplier_code', True),
    ):
        ModuleSetting.objects.update_or_create(
            module='suppliers',
            key=key,
            defaults={
                'label': key,
                'description': '',
                'default_value': default,
                'value': default,
            },
        )


class SupplierModuleSettingsUnitTests(TestCase):
    def setUp(self):
        cache.clear()
        _seed_all_supplier_flags()

    def test_representation_and_write_flags_strip_fields_and_defaults(self):
        for key in (
            'show_supplier_code',
            'show_supplier_type',
            'show_contact_details',
            'show_business_details',
            'show_payment_terms',
            'show_credit_fields',
            'show_supplier_rating',
            'show_preferred_flag',
            'show_supplier_notes',
            'show_supplier_status',
        ):
            SettingsService.set('suppliers', key, False)

        data = apply_supplier_representation_flags({
            'supplier_code': 'SC',
            'supplier_type': 'business',
            'contact_person': 'A',
            'email': 'a@t.com',
            'phone': '0700',
            'alternate_phone': '0701',
            'address': 'St',
            'city': 'Nairobi',
            'state': 'NRB',
            'country': 'KE',
            'postal_code': '00100',
            'full_address': 'full',
            'primary_contact': 'pc',
            'tax_id': 'T',
            'registration_number': 'R',
            'website': 'https://x.com',
            'payment_terms': 'net_30',
            'credit_limit': '1',
            'account_balance': '0',
            'is_credit_available': True,
            'rating': 5,
            'is_preferred': True,
            'notes': 'n',
            'is_active': True,
        })
        for key in (
            'supplier_code', 'supplier_type', 'contact_person', 'email', 'phone',
            'alternate_phone', 'address', 'city', 'state', 'country', 'postal_code',
            'full_address', 'primary_contact', 'tax_id', 'registration_number',
            'website', 'payment_terms', 'credit_limit', 'account_balance',
            'is_credit_available', 'rating', 'is_preferred', 'notes', 'is_active',
        ):
            self.assertNotIn(key, data)

        attrs = validate_supplier_write({})
        self.assertEqual(attrs['supplier_type'], 'business')
        self.assertEqual(attrs['payment_terms'], 'net_30')

        self.assertFalse(suppliers_show_supplier_code())
        self.assertTrue(suppliers_enable_edit())
        SettingsService.set('suppliers', 'enable_supplier_edit', False)
        self.assertFalse(suppliers_enable_edit())
        SettingsService.set('suppliers', 'enable_supplier_delete', False)
        self.assertFalse(suppliers_enable_delete())
        SettingsService.set('suppliers', 'enable_supplier_statistics', False)
        self.assertFalse(suppliers_enable_statistics())
        SettingsService.set('suppliers', 'enable_supplier_products', False)
        self.assertFalse(suppliers_enable_products())


class SupplierModelAndSerializerUnitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sup_unit', password='x')

    def test_model_properties_and_serializer_phones(self):
        supplier = Supplier.objects.create(
            name='Prop Co',
            contact_person='Jane',
            phone='254700111222',
            credit_limit=Decimal('1000.00'),
            account_balance=Decimal('200.00'),
            created_by=self.user,
        )
        self.assertIn('Jane', supplier.primary_contact)
        self.assertTrue(supplier.is_credit_available)
        supplier.credit_limit = Decimal('0')
        self.assertFalse(supplier.is_credit_available)

        ser = SupplierSerializer(
            data={
                'name': 'Alt Phone Co',
                'supplier_type': 'business',
                'alternate_phone': '0712345678',
            },
        )
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_build_queryset_search_exception_returns_empty(self):
        service = SupplierService()
        Supplier.objects.create(name='Search Me', created_by=self.user)
        with patch('suppliers.services.Q', side_effect=RuntimeError('filter failed')):
            broken = service.build_queryset({'search': 'Search'})
            self.assertEqual(broken.count(), 0)


class HasSupplierPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()

    def setUp(self):
        self.perm = HasSupplierPermission()
        self.view = MagicMock()

    def test_unauthenticated_denied(self):
        request = MagicMock()
        request.user = AnonymousUser()
        self.assertFalse(self.perm.has_permission(request, self.view))

    def test_admin_profile_and_custom_create_permission(self):
        admin_user = User.objects.create_user('sup_adm', password='x')
        UserProfile.objects.create(user=admin_user, role='admin', is_active=True)
        request = MagicMock()
        request.user = admin_user
        self.assertTrue(self.perm.has_permission(request, self.view))

        custom_user = User.objects.create_user('sup_custom', password='x')
        role = Role.objects.create(name='SupplierCreatorOnly', is_active=True)
        perm = Permission.objects.get(module='suppliers', action='create')
        role.permissions.add(perm)
        UserProfile.objects.create(
            user=custom_user,
            role='cashier',
            custom_role=role,
            is_active=True,
        )
        request.user = custom_user
        self.assertTrue(self.perm.has_permission(request, self.view))

        denied = User.objects.create_user('sup_denied', password='x')
        UserProfile.objects.create(user=denied, role='cashier', is_active=True)
        request.user = denied
        self.assertFalse(self.perm.has_permission(request, self.view))

        update_user = User.objects.create_user('sup_upd', password='x')
        upd_role = Role.objects.create(name='SupplierUpdaterOnly', is_active=True)
        upd_perm = Permission.objects.get(module='suppliers', action='update')
        upd_role.permissions.add(upd_perm)
        UserProfile.objects.create(
            user=update_user,
            role='cashier',
            custom_role=upd_role,
            is_active=True,
        )
        request.user = update_user
        self.assertTrue(self.perm.has_permission(request, self.view))

        staff_user = User.objects.create_user('sup_staff', password='x', is_staff=True)
        request.user = staff_user
        self.assertTrue(self.perm.has_permission(request, self.view))


class SupplierAdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser('sup_admin', 'a@t.com', 'x')
        self.admin = SupplierAdmin(Supplier, self.site)

    def test_save_model_sets_created_by_on_create(self):
        request = self.factory.post('/')
        request.user = self.user
        obj = Supplier(name='Admin Created')
        self.admin.save_model(request, obj, form=None, change=False)
        self.assertEqual(obj.created_by, self.user)


class SupplierViewSetUnitTests(TestCase):
    def test_destroy_action_permissions(self):
        view = SupplierViewSet()
        view.action = 'destroy'
        classes = [type(p) for p in view.get_permissions()]
        from accounts.permissions import IsAdmin, HasModuleAccess
        from rest_framework.permissions import IsAuthenticated

        self.assertIn(IsAuthenticated, classes)
        self.assertIn(HasModuleAccess, classes)
        self.assertIn(IsAdmin, classes)


class SupplierCoverageAPITests(SuperAdminAPITestCase):
    base_url = '/api/suppliers/suppliers/'

    def setUp(self):
        super().setUp()
        _seed_all_supplier_flags()
        ModuleSettings.objects.update_or_create(
            module_name='suppliers',
            defaults={'description': 'Suppliers', 'is_enabled': True},
        )
        self.supplier = Supplier.objects.create(
            name='Coverage Vendor',
            supplier_type='business',
            rating=4,
            is_active=True,
            account_balance=Decimal('100.00'),
        )

    def test_edit_and_delete_forbidden_when_disabled(self):
        SettingsService.set('suppliers', 'enable_supplier_edit', False)
        response = self.client.put(
            f'{self.base_url}{self.supplier.id}/',
            {
                'name': self.supplier.name,
                'supplier_type': 'business',
                'phone': '0700111222',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.patch(
            f'{self.base_url}{self.supplier.id}/',
            {'phone': '0700111222'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        SettingsService.set('suppliers', 'enable_supplier_edit', True)
        SettingsService.set('suppliers', 'enable_supplier_delete', False)
        response = self.client.delete(f'{self.base_url}{self.supplier.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_destroy_when_enabled(self):
        doomed = Supplier.objects.create(name='To Delete', supplier_type='business')
        response = self.client.delete(f'{self.base_url}{doomed.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Supplier.objects.filter(pk=doomed.id).exists())

    def test_list_min_rating_filter_and_invalid_value(self):
        response = self.client.get(f'{self.base_url}?min_rating=3')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_bad = self.client.get(f'{self.base_url}?min_rating=not-int')
        self.assertEqual(response_bad.status_code, status.HTTP_200_OK)

    def test_statistics_when_module_disabled(self):
        ModuleSettings.objects.filter(module_name='suppliers').update(is_enabled=False)
        response = self.client.get(f'{self.base_url}statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_suppliers'], 0)

    def test_statistics_hides_credit_and_handles_service_error(self):
        SettingsService.set('suppliers', 'show_credit_fields', False)
        response = self.client.get(f'{self.base_url}statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('total_account_balance', response.data)

        with patch.object(
            SupplierService,
            'get_all_supplier_statistics',
            side_effect=RuntimeError('stats boom'),
        ):
            response = self.client.get(f'{self.base_url}statistics/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)

    def test_products_list_for_supplier(self):
        Product.objects.create(
            name='Linked Product',
            sku='SUP-COV-1',
            price=Decimal('10.00'),
            supplier=self.supplier,
        )
        response = self.client.get(f'{self.base_url}{self.supplier.id}/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_products_forbidden_when_module_disabled(self):
        ModuleSettings.objects.filter(module_name='suppliers').update(is_enabled=False)
        response = self.client.get(f'{self.base_url}{self.supplier.id}/products/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SupplierManagerPermissionAPITests(ManagerAPITestCase):
    def setUp(self):
        super().setUp()
        _seed_all_supplier_flags()

    def test_manager_can_create_via_has_supplier_permission(self):
        response = self.client.post(
            '/api/suppliers/suppliers/',
            {'name': 'Mgr Vendor', 'supplier_type': 'business'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
