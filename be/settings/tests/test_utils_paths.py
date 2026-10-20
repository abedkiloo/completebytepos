"""Direct path coverage for settings.utils with a SimpleNamespace request."""

from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase

from settings.models import Branch, ModuleFeature, ModuleSettings, Tenant
from settings.utils import (
    get_current_branch,
    get_current_tenant,
    is_branch_support_enabled,
    set_current_branch,
    set_current_tenant,
)


class _Session(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modified = False

    def pop(self, key, default=None):
        self.modified = True
        return super().pop(key, default)


def _req(**kwargs):
    base = {
        'session': _Session(),
        'META': {},
        'query_params': {},
        'GET': {},
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _enable_branches(on=True):
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
            'is_enabled': on,
            'display_order': 1,
        },
    )


class UtilsPathCoverageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('utils_path', password='x')
        self.tenant = Tenant.objects.create(
            name='Path Co',
            code='PATH',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
        )
        self.hq = Branch.objects.create(
            tenant=self.tenant,
            branch_code='PHQ',
            name='Path HQ',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.user,
        )
        self.store = Branch.objects.create(
            tenant=self.tenant,
            branch_code='PST',
            name='Path Store',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=False,
            created_by=self.user,
        )
        _enable_branches(True)

    def test_set_get_clear_tenant_session(self):
        request = _req()
        set_current_tenant(request, self.tenant)
        self.assertEqual(request.session['current_tenant_id'], self.tenant.id)
        self.assertTrue(request.session.modified)
        self.assertEqual(get_current_tenant(request), self.tenant)
        set_current_tenant(request, None)
        self.assertNotIn('current_tenant_id', request.session)

    def test_tenant_query_invalid_and_missing(self):
        request = _req(query_params={'tenant_id': 'abc'})
        # falls through to default active tenant
        self.assertEqual(get_current_tenant(request), self.tenant)
        request = _req(query_params={'tenant_id': '999999'})
        self.assertEqual(get_current_tenant(request), self.tenant)
        Tenant.objects.all().update(is_active=False)
        self.assertIsNone(get_current_tenant(_req()))

    def test_tenant_from_query_success(self):
        request = _req(query_params={'tenant_id': str(self.tenant.id)})
        self.assertEqual(get_current_tenant(request), self.tenant)

    def test_set_get_clear_branch_session(self):
        request = _req()
        set_current_branch(request, self.store)
        self.assertEqual(get_current_branch(request, self.tenant), self.store)
        set_current_branch(request, None)
        self.assertEqual(get_current_branch(request, self.tenant), self.hq)

    def test_branch_header_and_query_and_mismatches(self):
        request = _req(META={'HTTP_X_BRANCH_ID': str(self.store.id)})
        self.assertEqual(get_current_branch(request, self.tenant), self.store)

        request = _req(META={'HTTP_X_BRANCH_ID': 'nope'})
        self.assertEqual(get_current_branch(request, self.tenant), self.hq)

        foreign = Tenant.objects.create(
            name='Foreign Path',
            code='FPTH',
            country='Kenya',
            owner=self.user,
            created_by=self.user,
        )
        foreign_b = Branch.objects.create(
            tenant=foreign,
            branch_code='FB',
            name='Foreign',
            city='Kisumu',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.user,
        )
        request = _req(META={'HTTP_X_BRANCH_ID': str(foreign_b.id)})
        self.assertEqual(get_current_branch(request, self.tenant), self.hq)

        request = _req(query_params={'branch_id': str(self.store.id)})
        self.assertEqual(get_current_branch(request, self.tenant), self.store)

        request = _req(query_params={'branch_id': str(foreign_b.id)})
        self.assertEqual(get_current_branch(request, self.tenant), self.hq)

        request = _req(query_params={'branch_id': 'bad'})
        self.assertEqual(get_current_branch(request, self.tenant), self.hq)

    def test_branch_fallbacks_without_tenant_or_hq(self):
        Branch.objects.filter(is_headquarters=True).update(is_headquarters=False)
        request = _req()
        # first active for tenant
        branch = get_current_branch(request, self.tenant)
        self.assertIsNotNone(branch)

        Branch.objects.all().delete()
        self.assertIsNone(get_current_branch(request, self.tenant))
        # no tenant, no branches
        self.assertIsNone(get_current_branch(request, None))

    def test_branch_disabled(self):
        _enable_branches(False)
        self.assertFalse(is_branch_support_enabled())
        self.assertIsNone(get_current_branch(_req(), self.tenant))
