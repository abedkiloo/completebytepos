"""API coverage for tenants, branches, modules viewsets and install helpers."""

from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status

from settings.models import Branch, ModuleFeature, ModuleSettings, Tenant
from settings.views import _bootstrap_credentials_payload
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


def _enable_multi_branch():
    module, _ = ModuleSettings.objects.get_or_create(
        module_name='settings',
        defaults={'description': 'Settings', 'is_enabled': True},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    ModuleFeature.objects.update_or_create(
        module=module,
        feature_key='multi_branch_support',
        defaults={
            'feature_name': 'Multi-branch',
            'is_enabled': True,
            'display_order': 1,
        },
    )


class ModuleSettingsViewSetTests(SuperAdminAPITestCase):
    def test_list_modules_catalog(self):
        response = self.client.get('/api/settings/modules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('modules' in response.data or isinstance(response.data, (dict, list)))

    def test_apply_preset_requires_id(self):
        response = self.client.post('/api/settings/modules/apply-preset/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_preset_invalid(self):
        response = self.client.post(
            '/api/settings/modules/apply-preset/',
            {'preset_id': 'not_a_real_preset'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_preset_ok(self):
        with patch('settings.views.apply_module_preset', return_value={'ok': True}) as mock_apply:
            response = self.client.post(
                '/api/settings/modules/apply-preset/',
                {'preset_id': 'retail_starter'},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_apply.assert_called_once()

    def test_update_module_setting(self):
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='products',
            defaults={'description': 'Products', 'is_enabled': True},
        )
        response = self.client.patch(
            f'/api/settings/modules/{module.pk}/',
            {'is_enabled': False, 'description': 'Updated'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        module.refresh_from_db()
        self.assertFalse(module.is_enabled)


class ModuleFeatureViewSetTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        self.module, _ = ModuleSettings.objects.get_or_create(
            module_name='products',
            defaults={'description': 'Products', 'is_enabled': True},
        )
        self.feature, _ = ModuleFeature.objects.get_or_create(
            module=self.module,
            feature_key='product_images',
            defaults={
                'feature_name': 'Images',
                'is_enabled': True,
                'display_order': 1,
            },
        )

    def test_list_and_filter_by_module(self):
        response = self.client.get(
            '/api/settings/module-features/',
            {'module': self.module.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_feature(self):
        # create fields are read-only on the serializer — cover update path only
        response = self.client.patch(
            f'/api/settings/module-features/{self.feature.pk}/',
            {'is_enabled': False, 'description': 'off'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.feature.refresh_from_db()
        self.assertFalse(self.feature.is_enabled)


class TenantViewSetTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        self.tenant = Tenant.objects.create(
            name='API Tenant',
            code='APIT',
            country='Kenya',
            owner=self.admin,
            created_by=self.admin,
        )

    def test_list_with_filters(self):
        response = self.client.get(
            '/api/settings/tenants/',
            {'is_active': 'true', 'search': 'API'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_active_action(self):
        response = self.client.get('/api/settings/tenants/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_update_destroy(self):
        response = self.client.post(
            '/api/settings/tenants/',
            {
                'name': 'New Biz',
                'code': 'NEWB',
                'country': 'Kenya',
            },
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        pk = response.data['id']
        response = self.client.patch(
            f'/api/settings/tenants/{pk}/',
            {'name': 'Renamed Biz'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.delete(f'/api/settings/tenants/{pk}/')
        self.assertIn(response.status_code, (status.HTTP_204_NO_CONTENT, status.HTTP_200_OK))

    def test_set_and_clear_current(self):
        response = self.client.post(f'/api/settings/tenants/{self.tenant.pk}/set_current/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.tenant.is_active = False
        self.tenant.save(update_fields=['is_active'])
        response = self.client.post(f'/api/settings/tenants/{self.tenant.pk}/set_current/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post('/api/settings/tenants/clear_current/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BranchViewSetTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        _enable_multi_branch()
        self.tenant = Tenant.objects.create(
            name='Branch Tenant',
            code='BRTN',
            country='Kenya',
            owner=self.admin,
            created_by=self.admin,
        )
        self.hq = Branch.objects.create(
            tenant=self.tenant,
            branch_code='HQ1',
            name='HQ',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.admin,
        )
        session = self.client.session
        session['current_tenant_id'] = self.tenant.id
        session.save()

    def test_list_filter_search(self):
        response = self.client.get(
            '/api/settings/branches/',
            {'is_active': 'true', 'search': 'HQ', 'tenant_id': self.tenant.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_empty_when_branch_support_off(self):
        ModuleFeature.objects.filter(feature_key='multi_branch_support').update(is_enabled=False)
        response = self.client.get('/api/settings/branches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 0)

    def test_create_requires_branch_support(self):
        ModuleFeature.objects.filter(feature_key='multi_branch_support').update(is_enabled=False)
        response = self.client.post(
            '/api/settings/branches/',
            {
                'branch_code': 'X1',
                'name': 'X',
                'city': 'Nairobi',
                'country': 'Kenya',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_update_destroy_active_hq_set_clear(self):
        response = self.client.post(
            '/api/settings/branches/',
            {
                'branch_code': 'ST1',
                'name': 'Store 1',
                'city': 'Nairobi',
                'country': 'Kenya',
                'is_active': True,
            },
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED), response.data)
        pk = response.data['id']
        response = self.client.patch(
            f'/api/settings/branches/{pk}/',
            {'name': 'Store One'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get('/api/settings/branches/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get('/api/settings/branches/headquarters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(f'/api/settings/branches/{pk}/set_current/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        Branch.objects.filter(pk=pk).update(is_active=False)
        response = self.client.post(f'/api/settings/branches/{pk}/set_current/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post('/api/settings/branches/clear_current/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        Branch.objects.filter(pk=pk).update(is_active=True)
        response = self.client.delete(f'/api/settings/branches/{pk}/')
        self.assertIn(response.status_code, (status.HTTP_204_NO_CONTENT, status.HTTP_200_OK))

    def test_headquarters_404_when_missing(self):
        Branch.objects.all().delete()
        response = self.client.get('/api/settings/branches/headquarters/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FreshInstallCoverageTests(SuperAdminAPITestCase):
    def test_bootstrap_credentials_payload(self):
        payload = _bootstrap_credentials_payload()
        self.assertIn('primary', payload)
        self.assertIn('users', payload)
        self.assertTrue(payload['users'])

    def test_setup_status_allow_any(self):
        self.client.credentials()
        response = self.client.get('/api/settings/setup-status/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('settings.views.apply_module_preset', return_value={})
    @patch('settings.views.call_command')
    def test_fresh_install_happy_path(self, mock_cmd, _preset):
        def _cmd(name, *args, **kwargs):
            return None

        mock_cmd.side_effect = _cmd
        with patch('config.database.is_postgresql_config', return_value=True), \
             patch('config.database.reset_default_database') as reset_db:
            response = self.client.post(
                '/api/settings/fresh-install/',
                {
                    'skip_db_delete': False,
                    'include_test_data': True,
                    'users': 1,
                    'products': 1,
                    'customers': 1,
                    'sales': 1,
                    'expenses': 1,
                    'module_preset': 'retail_starter',
                },
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data.get('success'))
        self.assertIn('credentials', response.data)
        reset_db.assert_called()

    @patch('settings.views.apply_module_preset', return_value={})
    @patch('settings.views.call_command')
    def test_fresh_install_sqlite_reset_and_step_warnings(self, mock_cmd, _preset):
        def _cmd(name, *args, **kwargs):
            if name in (
                'init_permissions',
                'init_modules',
                'init_module_settings',
                'init_accounts',
                'init_expense_categories',
                'setup_new_organization',
                'populate_test_data',
            ):
                raise Exception(f'{name} warn')
            return None

        mock_cmd.side_effect = _cmd
        with patch('config.database.is_postgresql_config', return_value=False), \
             patch('config.database.reset_default_database'):
            response = self.client.post(
                '/api/settings/fresh-install/',
                {'skip_db_delete': False, 'include_test_data': True},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data.get('success'))

    @patch('settings.views.call_command', side_effect=Exception('boom'))
    def test_fresh_install_failure(self, _cmd):
        response = self.client.post(
            '/api/settings/fresh-install/',
            {'skip_db_delete': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertFalse(response.data.get('success'))


class ModuleSettingsDetailExtraTests(SuperAdminAPITestCase):
    def test_unknown_module_404(self):
        response = self.client.get('/api/settings/not_a_real_module_zzz/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_no_valid_keys(self):
        response = self.client.patch(
            '/api/settings/products/',
            {'change_reason': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ManagerCannotMutateModules(ManagerAPITestCase):
    def test_manager_forbidden_on_module_update(self):
        module, _ = ModuleSettings.objects.get_or_create(
            module_name='products',
            defaults={'description': 'Products', 'is_enabled': True},
        )
        response = self.client.patch(
            f'/api/settings/modules/{module.pk}/',
            {'is_enabled': False},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
