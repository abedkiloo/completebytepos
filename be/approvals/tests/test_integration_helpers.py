"""Unit tests for approvals integration helpers and registry classifiers."""

from unittest.mock import Mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_SUPER_ADMIN, sync_default_roles
from approvals.category_integration import queue_category_deactivate, queue_category_delete
from approvals.models import PendingChange
from approvals.registry import (
    ACTION_CATEGORY_DEACTIVATE,
    ACTION_CATEGORY_DELETE,
    ACTION_PRODUCT_DEACTIVATE,
    ACTION_PRODUCT_PRICE,
    ACTION_PRODUCT_STOCK,
    ACTION_PRODUCT_TAX,
    ACTION_PRODUCT_UNIT,
    CHECKER_MODULE_BY_ACTION,
    classify_product_field_changes,
    classify_variant_field_changes,
)
from approvals.settings_integration import (
    classify_store_settings_changes,
    queue_module_settings_patch,
    queue_role_permission_assign,
    queue_store_settings_patch,
)
from approvals.tests.test_maker_checker import _enable_maker_checker
from approvals.variant_integration import (
    queue_variant_delete,
    queue_variant_sensitive_update,
    split_variant_payload,
)
from decimal import Decimal

from products.models import Category, Product
from settings.models import StoreSettings


def _request(data, user):
    req = Mock()
    req.data = data
    req.user = user
    req.META = {}
    return req


class RegistryClassifierTests(TestCase):
    def test_classify_product_and_variant_changes(self):
        self.assertIn(
            ACTION_PRODUCT_PRICE,
            classify_product_field_changes({'price': '10', 'mrp': '12'}),
        )
        self.assertIn(
            ACTION_PRODUCT_STOCK,
            classify_product_field_changes({'stock_quantity': 5}),
        )
        self.assertIn(
            ACTION_PRODUCT_DEACTIVATE,
            classify_product_field_changes({'is_active': False}),
        )
        self.assertIn(ACTION_PRODUCT_UNIT, classify_product_field_changes({'unit': 'kg'}))
        self.assertIn(ACTION_PRODUCT_TAX, classify_product_field_changes({'tax_rate': '16'}))
        self.assertEqual(classify_variant_field_changes({'name': 'x'}), [])
        self.assertTrue(CHECKER_MODULE_BY_ACTION[ACTION_PRODUCT_PRICE])

    def test_classify_store_settings_skips_unknown_keys(self):
        grouped = classify_store_settings_changes(
            {'unknown_flag': True},
            submitted_keys={'unknown_flag'},
        )
        self.assertEqual(grouped, {})


class VariantIntegrationUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('var_int', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.cat = Category.objects.create(name='C', is_active=True)
        cls.product = Product.objects.create(
            name='P',
            sku='P-1',
            category=cls.cat,
            price=Decimal('10'),
            stock_quantity=1,
            is_active=True,
        )

    def setUp(self):
        _enable_maker_checker(enabled=True)
        PendingChange.objects.all().delete()

    def test_split_variant_payload_respects_submitted_keys(self):
        sensitive, immediate = split_variant_payload(
            {'price': '20', 'name': 'Renamed'},
            submitted_keys={'price'},
        )
        self.assertEqual(sensitive, {'price': '20'})
        self.assertEqual(immediate, {'name': 'Renamed'})

    def test_queue_variant_returns_none_when_mc_disabled(self):
        _enable_maker_checker(enabled=False)
        variant = self.product.variants.create(
            sku='P-1-OFF', price=Decimal('10'), stock_quantity=1, is_active=True
        )
        self.assertIsNone(
            queue_variant_sensitive_update(
                _request({'reason': 'x'}, self.user),
                variant,
                {'price': '15'},
            )
        )

    def test_queue_variant_requires_reason(self):
        variant = self.product.variants.create(
            sku='P-1-V', price=Decimal('10'), stock_quantity=1, is_active=True
        )
        with self.assertRaises(ValidationError):
            queue_variant_sensitive_update(
                _request({}, self.user),
                variant,
                {'price': '15'},
            )

    def test_queue_variant_delete_requires_reason(self):
        variant = self.product.variants.create(
            sku='P-1-NR', price=Decimal('10'), stock_quantity=1, is_active=True
        )
        with self.assertRaises(ValidationError):
            queue_variant_delete(_request({}, self.user), variant)

    def test_queue_variant_delete_submits_pending(self):
        variant = self.product.variants.create(
            sku='P-1-D', price=Decimal('10'), stock_quantity=1, is_active=True
        )
        ch = queue_variant_delete(
            _request({'reason': 'Discontinued'}, self.user),
            variant,
        )
        self.assertEqual(ch.action_type, 'product_delete')
        self.assertEqual(ch.status, PendingChange.STATUS_PENDING)


class CategoryIntegrationUnitTests(TestCase):
    def test_queue_category_requires_mc_enabled(self):
        _enable_maker_checker(enabled=False)
        category = Category.objects.create(name='Off', is_active=True)
        with self.assertRaises(ValidationError):
            queue_category_deactivate(
                _request({'reason': 'x'}, User.objects.create_user('no_mc', password='x')),
                category,
            )


class CategoryIntegrationQueueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('cat_int', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )

    def setUp(self):
        _enable_maker_checker(enabled=True)
        PendingChange.objects.all().delete()

    def test_queue_category_requires_reason(self):
        category = Category.objects.create(name='NoReason', is_active=True)
        with self.assertRaises(ValidationError):
            queue_category_deactivate(_request({}, self.user), category)
        with self.assertRaises(ValidationError):
            queue_category_delete(_request({}, self.user), category)

    def test_queue_category_deactivate_and_delete(self):
        category = Category.objects.create(name='ToRemove', is_active=True)
        deact = queue_category_deactivate(
            _request({'reason': 'Season end'}, self.user),
            category,
        )
        self.assertEqual(deact.action_type, ACTION_CATEGORY_DEACTIVATE)
        delete_ch = queue_category_delete(
            _request({'change_reason': 'Obsolete'}, self.user),
            category,
        )
        self.assertEqual(delete_ch.action_type, ACTION_CATEGORY_DELETE)


class SettingsIntegrationQueueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('set_int', password='x')
        UserProfile.objects.create(
            user=cls.user,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )

    def setUp(self):
        _enable_maker_checker(enabled=True)
        PendingChange.objects.all().delete()

    def test_queue_store_settings_returns_none_when_no_sensitive_fields(self):
        store = StoreSettings.load()
        self.assertIsNone(
            queue_store_settings_patch(
                _request({}, self.user),
                store,
                {'maker_checker_enabled': True},
                submitted_keys={'maker_checker_enabled'},
                reason='toggle',
            )
        )

    def test_queue_store_settings_returns_none_when_mc_off(self):
        _enable_maker_checker(enabled=False)
        store = StoreSettings.load()
        self.assertIsNone(
            queue_store_settings_patch(
                _request({}, self.user),
                store,
                {'receipt_footer_text': 'Hi'},
                submitted_keys={'receipt_footer_text'},
                reason='x',
            )
        )

    def test_queue_store_settings_batches_multiple_actions(self):
        store = StoreSettings.load()
        ch = queue_store_settings_patch(
            _request({}, self.user),
            store,
            {
                'enabled_payment_methods': ['cash'],
                'receipt_footer_text': 'Thanks',
            },
            submitted_keys={'enabled_payment_methods', 'receipt_footer_text'},
            reason='Policy update',
        )
        self.assertIsNotNone(ch)
        self.assertEqual(
            PendingChange.objects.filter(status=PendingChange.STATUS_PENDING).count(),
            2,
        )

    def test_queue_module_returns_none_for_empty_updates(self):
        self.assertIsNone(
            queue_module_settings_patch(
                _request({}, self.user),
                module_name='products',
                updates={},
                reason='noop',
            )
        )

    def test_queue_role_permissions_requires_mc(self):
        _enable_maker_checker(enabled=False)
        role = Role.objects.get(name=ROLE_SUPER_ADMIN)
        with self.assertRaises(ValidationError):
            queue_role_permission_assign(
                _request({}, self.user),
                role,
                [1],
                reason='x',
            )

    def test_queue_module_and_role_permissions(self):
        ch = queue_module_settings_patch(
            _request({}, self.user),
            module_name='products',
            updates={'show_status': False},
            reason='Hide status toggles',
        )
        self.assertIsNotNone(ch)
        role = Role.objects.get(name=ROLE_SUPER_ADMIN)
        perm_ids = list(Permission.objects.values_list('id', flat=True)[:3])
        role_ch = queue_role_permission_assign(
            _request({}, self.user),
            role,
            perm_ids,
            reason='Trim permissions',
        )
        self.assertEqual(role_ch.action_type, 'role_permissions')
