"""CMS permission helper coverage."""

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from cms.permissions import CanManageWebsite, user_can_manage_website


class CmsPermissionsCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()

    def test_anonymous_and_no_profile_denied(self):
        self.assertFalse(user_can_manage_website(None))
        self.assertFalse(user_can_manage_website(AnonymousUser()))
        orphan = User.objects.create_user('cms_orphan', password='x')
        self.assertFalse(user_can_manage_website(orphan))

    def test_superuser_and_legacy_admin_allowed(self):
        su = User.objects.create_superuser('cms_su', 'su@x.com', 'x')
        self.assertTrue(user_can_manage_website(su))
        admin = User.objects.create_user('cms_admin', password='x')
        UserProfile.objects.create(user=admin, role='admin')
        self.assertTrue(user_can_manage_website(admin))

    def test_sales_denied_unless_website_manage(self):
        sales = User.objects.create_user('cms_sales', password='x')
        UserProfile.objects.create(
            user=sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )
        self.assertFalse(user_can_manage_website(sales))
        perm = CanManageWebsite()
        request = type('R', (), {'user': sales})()
        self.assertFalse(perm.has_permission(request, None))

    def test_super_admin_role_allowed(self):
        user = User.objects.create_user('cms_sa', password='x')
        UserProfile.objects.create(
            user=user,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
        )
        self.assertTrue(user_can_manage_website(user))

    def test_admin_named_custom_role_and_permission_exception(self):
        from unittest.mock import patch

        user = User.objects.create_user('cms_named_admin', password='x')
        admin_role = Role.objects.create(name='Administrator')
        UserProfile.objects.create(user=user, role='cashier', custom_role=admin_role)
        self.assertTrue(user_can_manage_website(user))

        broken = User.objects.create_user('cms_broken', password='x')
        profile = UserProfile.objects.create(
            user=broken,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
        )
        with patch.object(UserProfile, 'has_permission', side_effect=RuntimeError('x')):
            self.assertFalse(user_can_manage_website(broken))
