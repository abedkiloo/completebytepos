"""Eligibility for delivery assignment is the Delivery permission, not the role name."""

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import (
    ROLE_DELIVERY_AGENT,
    ROLE_DISPATCHER,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from delivery.assignees import (
    eligible_delivery_assignees,
    user_can_do_delivery,
    user_is_delivery_driver,
)


class DeliveryAssigneesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.sales = User.objects.create_user('asg_sales', password='x')
        UserProfile.objects.create(
            user=cls.sales,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.driver = User.objects.create_user('asg_drv', password='x')
        UserProfile.objects.create(
            user=cls.driver,
            role='delivery',
            custom_role=Role.objects.get(name=ROLE_DELIVERY_AGENT),
            is_active=True,
        )
        cls.dispatch = User.objects.create_user('asg_disp', password='x')
        UserProfile.objects.create(
            user=cls.dispatch,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_DISPATCHER),
            is_active=True,
        )
        cls.inactive = User.objects.create_user(
            'asg_off', password='x', is_active=False,
        )
        UserProfile.objects.create(
            user=cls.inactive,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.profile_off = User.objects.create_user('asg_poff', password='x')
        UserProfile.objects.create(
            user=cls.profile_off,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=False,
        )
        cls.orphan = User.objects.create_user('asg_orphan', password='x')

    def test_sales_and_driver_are_eligible_dispatcher_is_not(self):
        self.assertTrue(user_can_do_delivery(self.sales))
        self.assertTrue(user_is_delivery_driver(self.driver))
        self.assertFalse(user_can_do_delivery(self.dispatch))
        self.assertFalse(user_can_do_delivery(None))
        self.assertFalse(user_can_do_delivery(self.inactive))
        self.assertFalse(user_can_do_delivery(self.profile_off))
        self.assertFalse(user_can_do_delivery(self.orphan))

        ids = set(eligible_delivery_assignees().values_list('id', flat=True))
        self.assertIn(self.sales.id, ids)
        self.assertIn(self.driver.id, ids)
        self.assertNotIn(self.dispatch.id, ids)
        self.assertNotIn(self.inactive.id, ids)
        self.assertNotIn(self.profile_off.id, ids)
        self.assertNotIn(self.orphan.id, ids)

    def test_view_only_delivery_role_is_not_assignable(self):
        role = Role.objects.create(name='Route Viewer', is_active=True)
        role.permissions.add(
            Permission.objects.get(module='delivery', action='view'),
        )
        user = User.objects.create_user('asg_viewer', password='x')
        UserProfile.objects.create(
            user=user,
            role='cashier',
            custom_role=role,
            is_active=True,
        )
        self.assertFalse(user_can_do_delivery(user))
        ids = set(eligible_delivery_assignees().values_list('id', flat=True))
        self.assertNotIn(user.id, ids)

    def test_grant_sales_delivery_migration_reapplies(self):
        import importlib.util
        from pathlib import Path

        from django.apps import apps

        path = (
            Path(__file__).resolve().parents[2]
            / 'accounts'
            / 'migrations'
            / '0009_grant_sales_delivery.py'
        )
        spec = importlib.util.spec_from_file_location('grant_sales_delivery_mig', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        sales = Role.objects.get(name=ROLE_SALES)
        view = Permission.objects.get(module='delivery', action='view')
        update = Permission.objects.get(module='delivery', action='update')
        sales.permissions.remove(view, update)
        self.assertFalse(user_can_do_delivery(self.sales))
        mod.grant_sales_delivery(apps, None)
        self.assertTrue(user_can_do_delivery(self.sales))
        mod.ungrant_sales_delivery(apps, None)
        self.sales.profile.custom_role.refresh_from_db()
        self.assertFalse(user_can_do_delivery(self.sales))
        mod.grant_sales_delivery(apps, None)
        Permission.objects.filter(module='delivery', action__in=['view', 'update']).delete()
        mod.ungrant_sales_delivery(apps, None)
