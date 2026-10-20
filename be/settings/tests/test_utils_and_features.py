"""Unit tests for settings.utils and feature permission helpers."""

from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from settings.feature_permissions import RequireModuleFeature, feature_disabled_response
from settings.models import Branch, ModuleFeature, ModuleSettings, Tenant
from settings.module_features import is_module_feature_enabled, registry_default
from settings.utils import (
    get_current_branch,
    get_current_tenant,
    is_branch_support_enabled,
    set_current_branch,
    set_current_tenant,
)


def _enable_multi_branch(enabled=True):
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='settings',
        defaults={'description': 'Settings', 'is_enabled': True},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feature, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key='multi_branch_support',
        defaults={
            'feature_name': 'Multi-branch',
            'is_enabled': enabled,
            'display_order': 1,
        },
    )
    if feature.is_enabled != enabled:
        feature.is_enabled = enabled
        feature.save(update_fields=['is_enabled'])
    return module, feature


class BranchSupportUtilsTests(TestCase):
    def test_is_branch_support_enabled_false_without_module(self):
        ModuleSettings.objects.filter(module_name='settings').delete()
        self.assertFalse(is_branch_support_enabled())

    def test_is_branch_support_enabled_false_when_module_disabled(self):
        module, _ = _enable_multi_branch(True)
        module.is_enabled = False
        module.save(update_fields=['is_enabled'])
        self.assertFalse(is_branch_support_enabled())

    def test_is_branch_support_enabled_false_without_feature_row(self):
        ModuleSettings.objects.get_or_create(
            module_name='settings',
            defaults={'description': 'Settings', 'is_enabled': True},
        )
        ModuleFeature.objects.filter(feature_key='multi_branch_support').delete()
        self.assertFalse(is_branch_support_enabled())

    def test_is_branch_support_enabled_true(self):
        _enable_multi_branch(True)
        self.assertTrue(is_branch_support_enabled())


class TenantBranchSessionUtilsTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user('tenant_util', password='x')
        self.tenant = Tenant.objects.create(
            name='Util Co',
            code='UTIL',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
        )
        self.other = Tenant.objects.create(
            name='Other Co',
            code='OTHER',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
            is_active=False,
        )
        self.hq = Branch.objects.create(
            tenant=self.tenant,
            branch_code='HQ',
            name='HQ',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.user,
        )
        self.store = Branch.objects.create(
            tenant=self.tenant,
            branch_code='ST',
            name='Store',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=False,
            created_by=self.user,
        )
        _enable_multi_branch(True)

    def _request(self, path='/', **kwargs):
        django_request = self.factory.get(path, **kwargs)
        session = SessionStore()
        session.create()
        django_request.session = session
        django_request.user = self.user
        return Request(django_request)

    def test_get_current_tenant_from_session(self):
        request = self._request()
        set_current_tenant(request, self.tenant)
        self.assertEqual(get_current_tenant(request), self.tenant)

    def test_get_current_tenant_invalid_session_falls_through(self):
        request = self._request()
        request.session['current_tenant_id'] = 999999
        self.assertEqual(get_current_tenant(request), self.tenant)

    def test_get_current_tenant_from_header(self):
        request = self._request(HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(get_current_tenant(request), self.tenant)

    def test_get_current_tenant_invalid_header_ignored(self):
        request = self._request(HTTP_X_TENANT_ID='not-a-number')
        self.assertEqual(get_current_tenant(request), self.tenant)

    def test_get_current_tenant_from_query(self):
        request = self._request(f'/?tenant_id={self.tenant.id}')
        self.assertEqual(get_current_tenant(request), self.tenant)

    def test_get_current_tenant_none_when_no_active(self):
        Tenant.objects.all().update(is_active=False)
        request = self._request()
        self.assertIsNone(get_current_tenant(request))

    def test_set_current_tenant_clear(self):
        request = self._request()
        set_current_tenant(request, self.tenant)
        set_current_tenant(request, None)
        self.assertNotIn('current_tenant_id', request.session)

    def test_get_current_branch_disabled_returns_none(self):
        _enable_multi_branch(False)
        request = self._request()
        self.assertIsNone(get_current_branch(request, self.tenant))

    def test_get_current_branch_from_session(self):
        request = self._request()
        set_current_branch(request, self.store)
        self.assertEqual(get_current_branch(request, self.tenant), self.store)

    def test_get_current_branch_wrong_tenant_in_session(self):
        foreign = Tenant.objects.create(
            name='Foreign',
            code='FOR',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
        )
        foreign_branch = Branch.objects.create(
            tenant=foreign,
            branch_code='FX',
            name='Foreign HQ',
            city='Mombasa',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.user,
        )
        request = self._request()
        set_current_branch(request, foreign_branch)
        # Falls back to HQ for the requested tenant
        self.assertEqual(get_current_branch(request, self.tenant), self.hq)

    def test_get_current_branch_from_header(self):
        request = self._request(HTTP_X_BRANCH_ID=str(self.store.id))
        self.assertEqual(get_current_branch(request, self.tenant), self.store)

    def test_get_current_branch_from_query(self):
        request = self._request(f'/?branch_id={self.store.id}')
        self.assertEqual(get_current_branch(request, self.tenant), self.store)

    def test_get_current_branch_defaults_to_hq(self):
        request = self._request()
        self.assertEqual(get_current_branch(request, self.tenant), self.hq)

    def test_get_current_branch_without_tenant_uses_any_hq(self):
        request = self._request()
        Tenant.objects.exclude(pk=self.tenant.pk).delete()
        self.assertEqual(get_current_branch(request, tenant=None), self.hq)

    def test_set_current_branch_clear(self):
        request = self._request()
        set_current_branch(request, self.store)
        set_current_branch(request, None)
        self.assertNotIn('current_branch_id', request.session)


class FeaturePermissionsTests(TestCase):
    def test_require_module_feature_allows_when_enabled(self):
        ModuleSettings.objects.filter(module_name='products').delete()
        # Missing module → registry default (usually True)
        perm = RequireModuleFeature('products', 'product_images')
        factory = RequestFactory()
        request = factory.get('/')
        self.assertTrue(perm.has_permission(request, None))

    def test_require_module_feature_denies_when_module_off(self):
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='products',
            defaults={'description': 'Products', 'is_enabled': False},
        )
        module.is_enabled = False
        module.save(update_fields=['is_enabled'])
        ModuleFeature.objects.update_or_create(
            module=module,
            feature_key='product_images',
            defaults={
                'feature_name': 'Images',
                'is_enabled': True,
                'display_order': 1,
            },
        )
        perm = RequireModuleFeature('products', 'product_images')
        self.assertFalse(perm.has_permission(RequestFactory().get('/'), None))

    def test_feature_disabled_response_shape(self):
        payload = feature_disabled_response('sales', 'pos')
        self.assertIn('error', payload)
        self.assertIn('pos', payload['error'])
        self.assertIn('sales', payload['error'])

    def test_is_module_feature_enabled_uses_feature_row(self):
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='inventory',
            defaults={'description': 'Inventory', 'is_enabled': True},
        )
        module.is_enabled = True
        module.save(update_fields=['is_enabled'])
        ModuleFeature.objects.update_or_create(
            module=module,
            feature_key='low_stock_alerts',
            defaults={
                'feature_name': 'Low stock',
                'is_enabled': False,
                'display_order': 1,
            },
        )
        self.assertFalse(is_module_feature_enabled('inventory', 'low_stock_alerts'))

    def test_registry_default_unknown_is_true(self):
        self.assertTrue(registry_default('unknown_module_xyz', 'nope'))
