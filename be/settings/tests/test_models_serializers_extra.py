"""Extra model/serializer coverage for settings package."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from settings.models import (
    Branch,
    ModuleFeature,
    ModuleSetting,
    ModuleSettings,
    StoreSettings,
    Tenant,
)
from settings.module_catalog import apply_module_preset, build_modules_response
from settings.serializers import (
    BranchSerializer,
    ModuleFeatureSerializer,
    ModuleSettingsSerializer,
    TenantSerializer,
)
from settings.store_settings_helpers import normalize_payment_methods


class SettingsModelExtraTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sm_user', password='x')
        self.tenant = Tenant.objects.create(
            name='SM Co',
            code='SMCO',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
        )

    def test_module_settings_str_and_is_enabled(self):
        module = ModuleSettings.objects.create(
            module_name='products',
            description='Products',
            is_enabled=True,
        )
        self.assertIn('Enabled', str(module))
        self.assertTrue(ModuleSettings.is_module_enabled('products'))
        ModuleSettings.objects.filter(pk=module.pk).delete()
        self.assertTrue(ModuleSettings.is_module_enabled('products'))  # default True

    def test_module_feature_str_and_is_feature_enabled(self):
        module = ModuleSettings.objects.create(
            module_name='inventory',
            description='Inv',
            is_enabled=True,
        )
        feature = ModuleFeature.objects.create(
            module=module,
            feature_key='low_stock_alerts',
            feature_name='Low stock',
            is_enabled=True,
            display_order=1,
        )
        self.assertIn('Low stock', str(feature))
        self.assertTrue(ModuleFeature.is_feature_enabled('inventory', 'low_stock_alerts'))
        module.is_enabled = False
        module.save()
        self.assertFalse(ModuleFeature.is_feature_enabled('inventory', 'low_stock_alerts'))
        self.assertTrue(ModuleFeature.is_feature_enabled('missing', 'x'))

    def test_tenant_and_branch_helpers(self):
        self.assertIn('SM Co', str(self.tenant))
        self.assertEqual(Tenant.get_default_tenant(), self.tenant)
        hq = Branch.objects.create(
            tenant=self.tenant,
            branch_code='HQ',
            name='HQ',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.user,
        )
        other = Branch.objects.create(
            tenant=self.tenant,
            branch_code='B2',
            name='B2',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,  # save() clears previous HQ
            created_by=self.user,
        )
        hq.refresh_from_db()
        self.assertFalse(hq.is_headquarters)
        self.assertTrue(other.is_headquarters)
        self.assertIn('B2', str(other))
        self.assertEqual(Branch.get_headquarters(tenant=self.tenant), other)
        self.assertGreaterEqual(Branch.get_active_branches(tenant=self.tenant).count(), 2)

    def test_module_setting_and_store_str(self):
        row, _ = ModuleSetting.objects.update_or_create(
            module='products',
            key='show_status',
            defaults={
                'label': 'Show',
                'default_value': True,
                'value': True,
            },
        )
        self.assertEqual(str(row), 'products.show_status')
        store = StoreSettings.load()
        self.assertTrue(str(store))


class SettingsSerializerExtraTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ser_user', password='x')
        self.tenant = Tenant.objects.create(
            name='Ser Co',
            code='SERC',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
        )
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            branch_code='HQ',
            name='HQ',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.user,
        )

    def test_tenant_serializer_validate_code_and_phone(self):
        ser = TenantSerializer(data={
            'name': 'Dup',
            'code': 'SERC',
            'country': 'Kenya',
        })
        self.assertFalse(ser.is_valid())
        self.assertIn('code', ser.errors)

        ser = TenantSerializer(instance=self.tenant, data={
            'name': 'Ser Co',
            'code': 'SERC',
            'country': 'Kenya',
            'phone': '',
        }, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_branch_serializer_validation(self):
        ser = BranchSerializer(
            data={
                'branch_code': 'HQ',
                'name': 'Dup HQ',
                'city': 'Nairobi',
                'country': 'Kenya',
                'tenant_id': self.tenant.id,
            },
            context={'tenant_id': self.tenant.id},
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('branch_code', ser.errors)

        ser = BranchSerializer(
            data={
                'branch_code': 'NEW',
                'name': 'New',
                'city': 'Nairobi',
                'country': 'Kenya',
                'latitude': 100,
            },
            context={'tenant_id': self.tenant.id},
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('latitude', ser.errors)

        ser = BranchSerializer(
            data={
                'branch_code': 'NEW2',
                'name': 'New2',
                'city': 'Nairobi',
                'country': 'Kenya',
                'longitude': 200,
                'tenant_id': self.tenant.id,
            },
            context={'tenant_id': self.tenant.id},
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('longitude', ser.errors)

        ser = BranchSerializer(
            data={
                'branch_code': 'OK1',
                'name': 'Ok',
                'city': 'Nairobi',
                'country': 'Kenya',
                'latitude': '',
                'longitude': '',
                'phone': '',
                'tenant_id': self.tenant.id,
            },
            context={'tenant_id': self.tenant.id},
        )
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_module_serializers(self):
        module = ModuleSettings.objects.create(
            module_name='reports',
            description='Reports',
            is_enabled=True,
        )
        data = ModuleSettingsSerializer(module).data
        self.assertEqual(data['module_name'], 'reports')
        feature = ModuleFeature.objects.create(
            module=module,
            feature_key='enable_dashboard_summary',
            feature_name='Dashboard',
            is_enabled=True,
            display_order=1,
        )
        self.assertTrue(ModuleFeatureSerializer(feature).data['feature_key'])


class ModuleCatalogExtraTests(TestCase):
    def test_build_modules_response(self):
        data = build_modules_response()
        self.assertTrue(data)

    def test_apply_preset_unknown(self):
        with self.assertRaises(ValueError):
            apply_module_preset('totally_fake_preset')
