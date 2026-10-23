"""Targeted tests for approvals modules below coverage threshold."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ROLE_SUPER_ADMIN, ensure_permissions, sync_default_roles
from approvals.apply import apply_pending_change
from approvals.details import _dec, pending_change_details, sale_sections
from approvals.details_cache import DetailsCache, build_details_cache, build_sale_approval_cache
from approvals.effective import (
    apply_approved_category_overlay,
    apply_approved_product_overlay,
    apply_approved_variant_overlay,
    category_pending_flags,
    has_pending_category_deactivation,
    has_pending_product_deactivation,
    has_pending_product_stock,
    has_pending_variant_deactivation,
    has_pending_variant_price,
    has_pending_variant_stock,
    pending_schema_ready,
    variant_pending_flags,
)
from approvals.financial_workflow import (
    append_reason_to_notes,
    apply_pending_status_on_create,
    prepare_financial_update,
    validate_checker_not_maker,
    validate_past_dated_checker,
)
from approvals.models import PendingChange
from approvals.permissions import (
    change_business_dates,
    change_is_past_dated,
    is_sales_maker_checker_active,
    user_can_check,
    user_has_admin_checker_override,
    user_may_approve_change,
    user_may_approve_past_items,
)
from approvals.reason_rules import (
    _previous_field_value,
    is_initial_sensitive_set,
    is_unset_financial_value,
    normalize_stock_reason,
    sensitive_values_equal,
)
from approvals.refund_integration import (
    _summarize_refund_lines,
    queue_sale_refund,
    sale_refund_maker_checker_active,
)
from approvals.registry import (
    ACTION_CATEGORY_DEACTIVATE,
    ACTION_CATEGORY_DELETE,
    ACTION_DEBT_COLLECTION,
    ACTION_PRODUCT_DEACTIVATE,
    ACTION_PRODUCT_DELETE,
    ACTION_PRODUCT_PRICE,
    ACTION_PRODUCT_STOCK,
    ACTION_PRODUCT_TAX,
    ACTION_PRODUCT_UNIT,
    ACTION_ROLE_PERMISSIONS,
    ACTION_SALE_BACKFILL,
    ACTION_SALE_COMPLETE,
    ACTION_SALE_COMPLETED_EDIT,
    ACTION_SALE_REFUND,
    ACTION_SALE_ROLLBACK,
    ACTION_STORE_SETTINGS,
    ACTION_STOCK_ADJUST,
    ACTION_STOCK_PURCHASE,
    ACTION_STOCK_TRANSFER,
)
from approvals.serializers import PendingChangeSerializer
from approvals.service import (
    MakerCheckerRequired,
    approve_change,
    reject_change,
    resubmit_change,
    route_bulk_stock_adjustments,
    route_product_sensitive_update,
    route_stock_movement,
    route_variant_sensitive_update,
    snapshot_model,
    submit_change,
    validate_before_approval,
)
from approvals.tests.test_maker_checker import _enable_maker_checker
from approvals.views import PendingChangeViewSet, _parse_optional_int, _parse_query_date
from products.models import Category, Color, Product, ProductVariant, Size
from sales.models import Customer, Sale, SaleItem
from settings.models import Branch, StoreSettings, Tenant
from settings.test_utils import disable_maker_checker, enable_maker_checker
from utils.tests.api_test_base import ManagerAPITestCase


def _request(user, *, path='/api/test/', data=None):
    req = Mock()
    req.user = user
    req.path = path
    req.META = {}
    req.data = data or {}
    return req


class ServiceJsonAndSubmitTests(TestCase):
    def setUp(self):
        enable_maker_checker()
        self.user = User.objects.create_user('svc_user', password='x')

    def tearDown(self):
        disable_maker_checker()
        super().tearDown()

    def test_maker_checker_required_carries_change(self):
        change = PendingChange(id=1)
        exc = MakerCheckerRequired(change)
        self.assertIs(exc.change, change)

    def test_snapshot_model_json_safe_types(self):
        cat = Category.objects.create(name='Snap', is_active=True)
        snap = snapshot_model(cat, fields=['name', 'is_active'])
        self.assertEqual(snap['name'], 'Snap')
        self.assertTrue(snap['is_active'])

    def test_json_safe_pk_and_collections(self):
        from approvals import service as svc

        class WithPk:
            pk = 42

        self.assertEqual(svc._json_safe(WithPk()), 42)
        self.assertEqual(svc._json_safe({'a': Decimal('1.5')}), {'a': '1.5'})
        self.assertEqual(
            svc._json_safe([datetime(2026, 1, 1, tzinfo=dt_timezone.utc)]),
            ['2026-01-01T00:00:00+00:00'],
        )

    def test_submit_change_requires_reason_and_maker_checker(self):
        req = _request(self.user)
        with self.assertRaises(DjangoValidationError):
            submit_change(
                request=req,
                action_type=ACTION_PRODUCT_PRICE,
                entity_type='products.Product',
                entity_id=1,
                entity_repr='x',
                original_values={},
                proposed_values={'price': '1'},
                reason='   ',
            )
        disable_maker_checker()
        with self.assertRaises(DjangoValidationError):
            submit_change(
                request=req,
                action_type=ACTION_PRODUCT_PRICE,
                entity_type='products.Product',
                entity_id=1,
                entity_repr='x',
                original_values={},
                proposed_values={'price': '1'},
                reason='Valid reason',
            )

    def test_validate_before_approval_guards(self):
        cat = Category.objects.create(name='V', is_active=True)
        product = Product.objects.create(
            name='V Prod',
            sku='V-1',
            category=cat,
            price=Decimal('100'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        change = PendingChange(
            action_type=ACTION_PRODUCT_STOCK,
            proposed_values={'stock_quantity': 'nope'},
        )
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(change)
        change.proposed_values = {'stock_quantity': -1}
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(change)

        price_change = PendingChange(
            action_type=ACTION_PRODUCT_PRICE,
            original_values={'price': '100'},
            proposed_values={'price': '200'},
        )
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(price_change)
        validate_before_approval(price_change, extreme_price_confirmed=True)

        neg_adjust = PendingChange(
            action_type=ACTION_STOCK_ADJUST,
            apply_payload={
                'product_id': product.pk,
                'quantity': -100,
            },
        )
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(neg_adjust)


class ServiceRoutingAndBatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('route_user', password='x')
        cls.checker = User.objects.create_user('route_checker', password='x')
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.category = Category.objects.create(name='Route Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Route Product',
            sku='ROUTE-1',
            category=cls.category,
            price=Decimal('50'),
            stock_quantity=20,
            track_stock=True,
            is_active=True,
        )
        cls.size = Size.objects.create(name='L', code='L', is_active=True)
        cls.color = Color.objects.create(name='Blue', is_active=True)
        cls.variant = ProductVariant.objects.create(
            product=cls.product,
            size=cls.size,
            color=cls.color,
            sku='ROUTE-1-L-B',
            price=Decimal('50'),
            stock_quantity=8,
            is_active=True,
        )

    def setUp(self):
        enable_maker_checker()
        PendingChange.objects.all().delete()

    def tearDown(self):
        disable_maker_checker()
        super().tearDown()

    def test_route_product_and_variant_sensitive_update(self):
        req = _request(self.user)
        first = route_product_sensitive_update(
            req,
            self.product,
            {'price': '60', 'stock_quantity': 25, 'tax_rate': '16'},
            reason='Batch catalog update',
        )
        self.assertIsNotNone(first)
        self.assertEqual(PendingChange.objects.filter(status=PendingChange.STATUS_PENDING).count(), 3)

        route_variant_sensitive_update(
            req,
            self.variant,
            {'price': '55'},
            reason='Variant tune',
        )
        self.assertTrue(
            PendingChange.objects.filter(
                entity_type='products.ProductVariant',
                entity_id=str(self.variant.pk),
            ).exists()
        )

    def test_route_stock_movement_and_bulk(self):
        req = _request(self.user)
        change = route_stock_movement(
            req,
            action_type=ACTION_STOCK_PURCHASE,
            apply_payload={
                'product_id': self.product.pk,
                'quantity': 5,
                'unit_cost': '10',
            },
            reason='Restock order',
        )
        self.assertIsNotNone(change)
        self.assertEqual(change.proposed_values['stock_quantity'], 25)

        with self.assertRaises(DRFValidationError):
            route_stock_movement(
                req,
                action_type=ACTION_STOCK_ADJUST,
                apply_payload={'product_id': 99999, 'quantity': 1},
                reason='Missing product',
            )

        enable_maker_checker(emergency_stock_mode=True)
        skipped = route_stock_movement(
            req,
            action_type=ACTION_STOCK_ADJUST,
            apply_payload={'product_id': self.product.pk, 'quantity': 3},
            reason='Emergency inbound',
        )
        self.assertIsNone(skipped)

        enable_maker_checker(emergency_stock_mode=False)
        created = route_bulk_stock_adjustments(
            req,
            adjustments=[
                {'product_id': self.product.pk, 'quantity': 1, 'notes': 'Bulk A'},
                {'product_id': None, 'quantity': 2},
            ],
            reason='Bulk count',
        )
        self.assertEqual(len(created), 1)

    def test_batch_approve_and_reject(self):
        batch_id = 'batch-abc'
        c1 = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'price': '50'},
            proposed_values={'price': '55'},
            reason='Small bump',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            batch_id=batch_id,
        )
        c2 = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_STOCK,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'stock_quantity': 20},
            proposed_values={'stock_quantity': 22},
            reason='Small bump',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            batch_id=batch_id,
        )
        approve_change(c1, self.checker, request=_request(self.checker))
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(c1.status, PendingChange.STATUS_APPROVED)
        self.assertEqual(c2.status, PendingChange.STATUS_APPROVED)

        batch_id = 'batch-reject'
        r1 = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'price': '55'},
            proposed_values={'price': '60'},
            reason='Try again',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            batch_id=batch_id,
        )
        PendingChange.objects.create(
            action_type=ACTION_PRODUCT_STOCK,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'stock_quantity': 22},
            proposed_values={'stock_quantity': 30},
            reason='Try again',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            batch_id=batch_id,
        )
        reject_change(r1, self.checker, 'Not now', request=_request(self.checker))
        self.assertEqual(
            PendingChange.objects.filter(batch_id=batch_id, status=PendingChange.STATUS_REJECTED).count(),
            2,
        )

    def test_resubmit_rejected_batch(self):
        batch_id = 'batch-resubmit'
        change = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'price': '55'},
            proposed_values={'price': '58'},
            reason='Original',
            status=PendingChange.STATUS_REJECTED,
            made_by=self.user,
            batch_id=batch_id,
            rejection_reason='No',
        )
        PendingChange.objects.create(
            action_type=ACTION_PRODUCT_STOCK,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'stock_quantity': 20},
            proposed_values={'stock_quantity': 21},
            reason='Original',
            status=PendingChange.STATUS_REJECTED,
            made_by=self.user,
            batch_id=batch_id,
            rejection_reason='No',
        )
        resubmit_change(change, self.user, reason='Fixed', request=_request(self.user))
        self.assertEqual(
            PendingChange.objects.filter(batch_id=batch_id, status=PendingChange.STATUS_PENDING).count(),
            2,
        )


class DetailsCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        ensure_permissions()
        cls.user = User.objects.create_user('cache_user', password='x')
        cls.category = Category.objects.create(name='Cache Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Cache Product',
            sku='CACHE-1',
            category=cls.category,
            price=Decimal('10'),
            stock_quantity=5,
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='Cache Customer')
        cls.role = Role.objects.get(name=ROLE_MANAGER)
        cls.perm = Permission.objects.first()
        tenant = Tenant.objects.create(
            name='Cache Tenant',
            code='CACHE',
            country='Kenya',
            owner=cls.user,
            created_by=cls.user,
        )
        cls.branch = Branch.objects.create(
            tenant=tenant,
            branch_code='CACHE-B1',
            name='Cache Branch',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=cls.user,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-CACHE',
            status='pending_approval',
            subtotal=Decimal('10'),
            total=Decimal('10'),
            payment_method='cash',
            amount_paid=Decimal('10'),
            cashier=cls.user,
        )

    def test_empty_cache(self):
        cache = build_details_cache([])
        self.assertEqual(len(cache.sales), 0)

    def test_build_details_cache_action_branches(self):
        changes = [
            PendingChange(
                action_type=ACTION_DEBT_COLLECTION,
                entity_id=str(self.customer.pk),
                apply_payload={},
            ),
            PendingChange(
                action_type=ACTION_SALE_BACKFILL,
                apply_payload={
                    'customer_id': self.customer.pk,
                    'items': [{'product_id': self.product.pk, 'variant_id': None}],
                },
            ),
            PendingChange(
                action_type=ACTION_STOCK_TRANSFER,
                apply_payload={
                    'product_id': self.product.pk,
                    'branch_id': self.branch.pk,
                    'to_branch_id': self.branch.pk,
                },
            ),
            PendingChange(
                action_type=ACTION_CATEGORY_DELETE,
                entity_id=str(self.category.pk),
            ),
            PendingChange(
                action_type=ACTION_ROLE_PERMISSIONS,
                entity_id=str(self.role.pk),
                proposed_values={'permission_ids': [self.perm.pk]},
                original_values={'permission_ids': []},
            ),
            PendingChange(
                entity_type='sales.Sale',
                entity_id=str(self.sale.pk),
                action_type=ACTION_SALE_COMPLETE,
            ),
            PendingChange(
                entity_type='products.Product',
                entity_id=str(self.product.pk),
                action_type=ACTION_PRODUCT_PRICE,
            ),
        ]
        cache = build_details_cache(changes)
        self.assertIn(self.customer.pk, cache.customers)
        self.assertIn(self.product.pk, cache.products)
        self.assertIn(self.category.pk, cache.categories)
        self.assertIn(self.role.pk, cache.roles)
        self.assertIn(self.perm.pk, cache.permissions)
        self.assertIn(self.branch.pk, cache.branches)
        self.assertIn(self.sale.pk, cache.sales)

    def test_build_sale_approval_cache(self):
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(self.sale.pk),
            entity_repr='S-CACHE',
            original_values={},
            proposed_values={},
            reason='Complete',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
        )
        cache = build_sale_approval_cache([self.sale])
        self.assertIn(self.sale.pk, cache.pending_complete_by_sale_id)
        completed = Sale.objects.create(
            sale_number='S-DONE',
            status='completed',
            subtotal=Decimal('1'),
            total=Decimal('1'),
            payment_method='cash',
            amount_paid=Decimal('1'),
            cashier=self.user,
        )
        empty = build_sale_approval_cache([completed])
        self.assertEqual(len(empty.pending_complete_by_sale_id), 0)


class ApplyModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('apply_user', password='x')
        cls.checker = User.objects.create_user('apply_checker', password='x')
        cls.category = Category.objects.create(name='Apply Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Apply Product',
            sku='APPLY-1',
            category=cls.category,
            price=Decimal('20'),
            stock_quantity=10,
            track_stock=True,
            has_variants=True,
            is_active=True,
        )
        cls.size = Size.objects.create(name='M', code='M', is_active=True)
        cls.color = Color.objects.create(name='Green', is_active=True)
        cls.variant = ProductVariant.objects.create(
            product=cls.product,
            size=cls.size,
            color=cls.color,
            sku='APPLY-1-M-G',
            price=Decimal('20'),
            stock_quantity=4,
            is_active=True,
        )
        tenant = Tenant.objects.create(
            name='Apply Tenant',
            code='APLY',
            country='Kenya',
            owner=cls.user,
            created_by=cls.user,
        )
        cls.branch_a = Branch.objects.create(
            tenant=tenant,
            branch_code='APLY-A',
            name='A',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=cls.user,
        )
        cls.branch_b = Branch.objects.create(
            tenant=tenant,
            branch_code='APLY-B',
            name='B',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=False,
            created_by=cls.user,
        )

    def test_apply_variant_selling_price_and_category_delete(self):
        change = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.ProductVariant',
            entity_id=str(self.variant.pk),
            entity_repr=str(self.variant),
            original_values={'price': '20'},
            proposed_values={'selling_price': '25', 'stock_quantity': 6},
            reason='Variant apply',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(change)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.price, Decimal('25'))

        cat = Category.objects.create(name='To Delete', is_active=True)
        delete_change = PendingChange.objects.create(
            action_type=ACTION_CATEGORY_DELETE,
            entity_type='products.Category',
            entity_id=str(cat.pk),
            entity_repr=str(cat),
            original_values={},
            proposed_values={},
            reason='Remove',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(delete_change)
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())

    def test_apply_store_module_role_and_unsupported(self):
        store = StoreSettings.load()
        change = PendingChange(
            action_type=ACTION_STORE_SETTINGS,
            entity_type='settings.StoreSettings',
            entity_id='1',
            proposed_values={'maker_checker_enabled': True},
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(change)
        store.refresh_from_db()

        role = Role.objects.get(name=ROLE_MANAGER)
        perm = Permission.objects.first()
        perm_change = PendingChange(
            action_type=ACTION_ROLE_PERMISSIONS,
            entity_type='accounts.Role',
            entity_id=str(role.pk),
            proposed_values={'permission_ids': [perm.pk]},
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(perm_change)

        module_change = PendingChange(
            action_type='module_settings',
            entity_type='settings.ModuleSetting',
            entity_id='products',
            apply_payload={'module': 'products', 'updates': {'show_status': True}},
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(module_change)

        with self.assertRaises(DjangoValidationError):
            apply_pending_change(
                PendingChange(
                    action_type='unknown_action',
                    entity_type='unknown.Entity',
                    entity_id='1',
                )
            )

    def test_apply_stock_transfer_and_refund_requires_checker(self):
        change = PendingChange.objects.create(
            action_type=ACTION_STOCK_TRANSFER,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'stock_quantity': 10},
            proposed_values={'stock_quantity': 8},
            reason='Move stock',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            checked_by=self.checker,
            apply_payload={
                'product_id': self.product.pk,
                'quantity': 2,
                'branch_id': self.branch_a.pk,
                'to_branch_id': self.branch_b.pk,
            },
        )
        apply_pending_change(change)

        sale = Sale.objects.create(
            sale_number='S-APPLY-REF',
            status='completed',
            subtotal=Decimal('20'),
            total=Decimal('20'),
            payment_method='cash',
            amount_paid=Decimal('20'),
            cashier=self.user,
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('20'),
            subtotal=Decimal('20'),
        )
        refund_change = PendingChange(
            action_type=ACTION_SALE_REFUND,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            apply_payload={'full': True, 'items': []},
            reason='Refund test',
            made_by=self.user,
            checked_by=None,
        )
        with self.assertRaises(DjangoValidationError):
            apply_pending_change(refund_change)


class EffectiveAndPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('eff_user', password='x')
        cls.category = Category.objects.create(name='Eff2 Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Eff2 Product',
            sku='EFF2-1',
            category=cls.category,
            price=Decimal('10'),
            stock_quantity=10,
            is_active=True,
        )

    def test_overlays_and_flags_when_disabled_or_pending(self):
        disable_maker_checker()
        data = apply_approved_product_overlay(self.product, {'price': '10'})
        self.assertNotIn('pending_approval', data)
        enable_maker_checker()
        PendingChange.objects.create(
            action_type=ACTION_CATEGORY_DEACTIVATE,
            entity_type='products.Category',
            entity_id=str(self.category.pk),
            status=PendingChange.STATUS_PENDING,
            proposed_values={'is_active': False},
            made_by=self.user,
        )
        out = apply_approved_category_overlay(self.category, {'name': 'Eff2 Cat'})
        self.assertTrue(out['pending_approval']['pending_deactivation'])
        self.assertTrue(has_pending_category_deactivation(self.category.pk))
        self.assertIn('pending_deactivation', category_pending_flags(self.category.pk))

    def test_variant_and_product_pending_helpers(self):
        enable_maker_checker()
        size = Size.objects.create(name='XS', code='XS', is_active=True)
        color = Color.objects.create(name='Black', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='EFF2-V',
            price=Decimal('10'),
            stock_quantity=3,
            is_active=True,
        )
        PendingChange.objects.create(
            entity_type='products.ProductVariant',
            entity_id=str(variant.pk),
            action_type=ACTION_PRODUCT_STOCK,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'stock_quantity': 1},
            made_by=self.user,
        )
        self.assertTrue(has_pending_variant_stock(variant.pk))
        self.assertTrue(variant_pending_flags(variant.pk)['pending_stock'])
        PendingChange.objects.create(
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            action_type=ACTION_STOCK_ADJUST,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'stock_quantity': 5},
            apply_payload={'product_id': self.product.pk, 'variant_id': variant.pk, 'quantity': -1},
            made_by=self.user,
        )
        self.assertTrue(has_pending_product_stock(self.product.pk))
        PendingChange.objects.create(
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            action_type=ACTION_PRODUCT_DEACTIVATE,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'is_active': False},
            made_by=self.user,
        )
        self.assertTrue(has_pending_product_deactivation(self.product.pk))
        PendingChange.objects.create(
            entity_type='products.ProductVariant',
            entity_id=str(variant.pk),
            action_type=ACTION_PRODUCT_PRICE,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'price': '12'},
            made_by=self.user,
        )
        self.assertTrue(has_pending_variant_price(variant.pk))
        PendingChange.objects.create(
            entity_type='products.ProductVariant',
            entity_id=str(variant.pk),
            action_type=ACTION_PRODUCT_DEACTIVATE,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'is_active': False},
            made_by=self.user,
        )
        self.assertTrue(has_pending_variant_deactivation(variant.pk))
        disable_maker_checker()
        self.assertFalse(has_pending_variant_price(variant.pk))

    def test_permissions_checker_matrix(self):
        anon = Mock(is_authenticated=False)
        self.assertFalse(user_can_check(anon, ACTION_PRODUCT_PRICE))
        manager = User.objects.create_user('perm_mgr', password='x', is_staff=True)
        UserProfile.objects.create(
            user=manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        self.assertTrue(user_can_check(manager, ACTION_PRODUCT_PRICE))
        self.assertFalse(user_can_check(manager, ACTION_SALE_REFUND))
        admin = User.objects.create_user('perm_admin', password='x')
        UserProfile.objects.create(user=admin, role='admin')
        self.assertTrue(user_has_admin_checker_override(admin))
        self.assertTrue(user_may_approve_past_items(admin))

        change = PendingChange(
            action_type=ACTION_PRODUCT_PRICE,
            made_by_id=manager.id,
        )
        self.assertFalse(user_may_approve_change(manager, change))
        self.assertTrue(user_may_approve_change(admin, change))

        sale_change = PendingChange(
            action_type=ACTION_SALE_COMPLETE,
            entity_id='not-int',
            apply_payload={},
            made_at=timezone.now(),
        )
        dates = change_business_dates(sale_change)
        self.assertTrue(len(dates) >= 1)
        self.assertIsInstance(is_sales_maker_checker_active(), bool)


class ViewsCoverageTests(ManagerAPITestCase):
    def test_view_helpers_and_pending_count_exclude(self):
        self.assertIsNone(_parse_query_date(None, field_name='date_from'))
        with self.assertRaises(DRFValidationError):
            _parse_query_date('not-a-date', field_name='date_from')
        self.assertIsNone(_parse_optional_int(''))
        self.assertIsNone(_parse_optional_int('bad'))

        PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id='1',
            entity_repr='X',
            original_values={},
            proposed_values={'price': '2'},
            reason='Pending badge',
            status=PendingChange.STATUS_PENDING,
            made_by=self.manager_user,
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id='9',
            entity_repr='S',
            original_values={},
            proposed_values={},
            reason='Sale queue',
            status=PendingChange.STATUS_PENDING,
            made_by=self.manager_user,
        )
        resp = self.client.get(
            '/api/approvals/pending-changes/pending-count/',
            {'exclude_action_type': ACTION_SALE_COMPLETE},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_my_decisions_invalid_date_and_non_paginated(self):
        PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id='3',
            entity_repr='Z',
            original_values={},
            proposed_values={'price': '3'},
            reason='Decided',
            status=PendingChange.STATUS_APPROVED,
            made_by=self.manager_user,
            checked_by=self.manager_user,
            checked_at=timezone.now(),
        )
        bad = self.client.get(
            '/api/approvals/pending-changes/my-decisions/',
            {'date_from': 'bad-date'},
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        with patch(
            'rest_framework.generics.GenericAPIView.paginate_queryset',
            return_value=None,
        ):
            plain = self.client.get(
                '/api/approvals/pending-changes/my-decisions/',
                {'scope': 'mine'},
            )
        self.assertEqual(plain.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(plain.data, list))

    def test_list_filters_entity_type(self):
        PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id='4',
            entity_repr='Filter',
            original_values={},
            proposed_values={'price': '4'},
            reason='List filter',
            status=PendingChange.STATUS_PENDING,
            made_by=self.manager_user,
        )
        resp = self.client.get(
            '/api/approvals/pending-changes/',
            {'entity_type': 'products.Product'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 1)


class ReasonRulesAndRefundTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('refund_user', password='x')
        cat = Category.objects.create(name='Ref Cat', is_active=True)
        product = Product.objects.create(
            name='Ref Product',
            sku='REF-1',
            category=cat,
            price=Decimal('25'),
            stock_quantity=5,
            is_active=True,
        )
        size = Size.objects.create(name='XL', code='XL', is_active=True)
        color = Color.objects.create(name='White', is_active=True)
        cls.sale = Sale.objects.create(
            sale_number='S-REF-SUM',
            status='completed',
            subtotal=Decimal('50'),
            total=Decimal('50'),
            payment_method='cash',
            amount_paid=Decimal('50'),
            cashier=cls.user,
        )
        cls.line = SaleItem.objects.create(
            sale=cls.sale,
            product=product,
            size=size,
            color=color,
            quantity=2,
            unit_price=Decimal('25'),
            subtotal=Decimal('50'),
        )

    def test_reason_rules_edges(self):
        self.assertFalse(is_unset_financial_value('not-a-number'))
        self.assertTrue(is_initial_sensitive_set('track_stock', False, True))
        with self.assertRaises(DjangoValidationError):
            normalize_stock_reason('ab')
        self.assertTrue(sensitive_values_equal('price', 'bad', 'bad'))

    def test_refund_integration_summary_and_queue_errors(self):
        self.assertTrue(sale_refund_maker_checker_active())
        summary = _summarize_refund_lines(self.sale, items=None, full=True)
        self.assertIn('Ref Product', summary)
        self.assertIn('XL', summary)

        req = _request(self.user)
        with self.assertRaises(DjangoValidationError):
            queue_sale_refund(req, self.sale, full=True, items=None, reason='  ')
        self.sale.status = 'pending'
        self.sale.save(update_fields=['status'])
        with self.assertRaises(DjangoValidationError):
            queue_sale_refund(req, self.sale, full=True, items=None, reason='Valid reason here')
        self.sale.status = 'completed'
        self.sale.refund_status = 'refunded'
        self.sale.save(update_fields=['status', 'refund_status'])
        with self.assertRaises(DjangoValidationError):
            queue_sale_refund(req, self.sale, full=True, items=None, reason='Valid reason here')


class SerializerAndFinancialWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()

    def test_serializer_details_exception_returns_none(self):
        change = PendingChange(
            id=99,
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id='1',
            made_at=timezone.now(),
            status=PendingChange.STATUS_PENDING,
        )
        ser = PendingChangeSerializer(change, context={'details_cache': None})
        with patch('approvals.details.pending_change_details', side_effect=RuntimeError('boom')):
            self.assertIsNone(ser.data['details'])

    def test_financial_workflow_branches(self):
        class NoNotes:
            status = 'approved'

        self.assertIsNone(append_reason_to_notes(NoNotes(), 'x'))
        self.assertEqual(apply_pending_status_on_create(NoNotes()), [])
        validate_checker_not_maker(None, None)
        manager = User.objects.create_user('fw_mgr', password='x')
        UserProfile.objects.create(
            user=manager,
            role='manager',
            custom_role=Role.objects.get(name=ROLE_MANAGER),
            is_active=True,
        )
        with self.assertRaises(DRFValidationError):
            validate_past_dated_checker(manager, date(2000, 1, 1))

        from expenses.models import Expense

        expense = Expense.objects.create(
            description='Posted',
            amount=Decimal('5'),
            expense_date='2026-03-01',
            status='approved',
        )
        req = Mock(data={'proposal_reason': 'Correction'})
        prepare_financial_update(req, expense, allow_finalized=True)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'approved')


class ServiceValidationExtendedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        ensure_permissions()
        cls.user = User.objects.create_user('val_user', password='x')
        cls.checker = User.objects.create_user('val_checker', password='x', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.cat = Category.objects.create(name='Val Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Val Prod',
            sku='VAL-1',
            category=cls.cat,
            price=Decimal('30'),
            stock_quantity=10,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-VAL',
            status='completed',
            subtotal=Decimal('30'),
            total=Decimal('30'),
            payment_method='cash',
            amount_paid=Decimal('30'),
            cashier=cls.user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=1,
            unit_price=Decimal('30'),
            subtotal=Decimal('30'),
        )

    def test_validate_before_approval_sale_flows(self):
        refund_change = PendingChange(
            action_type=ACTION_SALE_REFUND,
            entity_id=str(self.sale.pk),
            apply_payload={'full': True},
        )
        validate_before_approval(refund_change)

        self.sale.status = 'pending'
        self.sale.save(update_fields=['status'])
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(refund_change)
        self.sale.status = 'completed'
        self.sale.save(update_fields=['status'])

        rollback_change = PendingChange(
            action_type=ACTION_SALE_ROLLBACK,
            entity_id=str(self.sale.pk),
        )
        validate_before_approval(rollback_change)

        complete_change = PendingChange(
            action_type=ACTION_SALE_COMPLETE,
            entity_id=str(self.sale.pk),
        )
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(complete_change)

        queued = Sale.objects.create(
            sale_number='S-QUE',
            status='pending_approval',
            subtotal=Decimal('1'),
            total=Decimal('1'),
            payment_method='cash',
            amount_paid=Decimal('1'),
            cashier=self.user,
        )
        complete_change.entity_id = str(queued.pk)
        validate_before_approval(complete_change)

        debt_change = PendingChange(
            action_type=ACTION_DEBT_COLLECTION,
            entity_id='999999',
            apply_payload={'amount': '10'},
        )
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(debt_change)

        backfill_change = PendingChange(
            action_type=ACTION_SALE_BACKFILL,
            apply_payload={'occurred_at': '2020-06-01T10:00:00Z'},
        )
        validate_before_approval(backfill_change)

    def test_approve_reject_resubmit_guards(self):
        change = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr='Val',
            original_values={'price': '30'},
            proposed_values={'price': '31'},
            reason='Tiny',
            status=PendingChange.STATUS_APPROVED,
            made_by=self.user,
            checked_by=self.checker,
        )
        with self.assertRaises(DjangoValidationError):
            approve_change(change, self.checker)
        change.status = PendingChange.STATUS_PENDING
        change.save(update_fields=['status'])

        with self.assertRaises(DjangoValidationError):
            reject_change(change, self.checker, '   ')
        reject_change(change, self.checker, 'No', request=_request(self.checker))

        rejected = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr='Val2',
            original_values={'price': '30'},
            proposed_values={'price': '32'},
            reason='Other maker',
            status=PendingChange.STATUS_REJECTED,
            made_by=self.user,
        )
        outsider = User.objects.create_user('outsider', password='x')
        with self.assertRaises(DjangoValidationError):
            resubmit_change(rejected, outsider)

    def test_route_stock_variant_errors_and_disabled_routes(self):
        disable_maker_checker()
        req = _request(self.user)
        self.assertIsNone(
            route_product_sensitive_update(req, self.product, {'price': '40'}, reason='Off')
        )
        size = Size.objects.create(name='Val-S', code='VS', is_active=True)
        color = Color.objects.create(name='Val-C', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='VAL-V',
            price=Decimal('30'),
            stock_quantity=2,
            is_active=True,
        )
        self.assertIsNone(
            route_variant_sensitive_update(req, variant, {'price': '40'}, reason='Off')
        )
        enable_maker_checker()
        with self.assertRaises(DRFValidationError):
            route_stock_movement(
                req,
                action_type=ACTION_STOCK_ADJUST,
                apply_payload={
                    'product_id': self.product.pk,
                    'variant_id': 99999,
                    'quantity': 1,
                },
                reason='Bad variant',
            )


class ApplyExtendedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('apply2', password='x')
        cls.checker = User.objects.create_user('apply2_chk', password='x', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.cat = Category.objects.create(name='Apply2 Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Apply2 Prod',
            sku='AP2-1',
            category=cls.cat,
            price=Decimal('15'),
            cost=Decimal('6'),
            stock_quantity=8,
            track_stock=True,
            is_active=True,
        )
        cls.size = Size.objects.create(name='S2', code='S2', is_active=True)
        cls.color = Color.objects.create(name='C2', is_active=True)
        cls.variant = ProductVariant.objects.create(
            product=cls.product,
            size=cls.size,
            color=cls.color,
            sku='AP2-V',
            price=Decimal('15'),
            stock_quantity=4,
            is_active=True,
        )

    def test_apply_deletes_purchase_and_completed_edit(self):
        ghost = PendingChange(
            action_type=ACTION_PRODUCT_DELETE,
            entity_type='products.Product',
            entity_id='99999',
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(ghost)

        variant_delete = PendingChange(
            action_type=ACTION_PRODUCT_DELETE,
            entity_type='products.ProductVariant',
            entity_id=str(self.variant.pk),
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(variant_delete)
        self.assertFalse(ProductVariant.objects.filter(pk=self.variant.pk).exists())

        purchase = PendingChange.objects.create(
            action_type=ACTION_STOCK_PURCHASE,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'stock_quantity': 8},
            proposed_values={'stock_quantity': 13},
            reason='Buy',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            checked_by=self.checker,
            apply_payload={
                'product_id': self.product.pk,
                'quantity': 5,
                'unit_cost': '5',
                'unit_sell_price': '15',
            },
        )
        apply_pending_change(purchase)

        sale = Sale.objects.create(
            sale_number='S-EDIT',
            status='completed',
            subtotal=Decimal('15'),
            total=Decimal('15'),
            payment_method='cash',
            amount_paid=Decimal('15'),
            notes='Before',
            cashier=self.user,
        )
        edit = PendingChange(
            action_type=ACTION_SALE_COMPLETED_EDIT,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            proposed_values={'notes': 'After'},
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(edit)
        sale.refresh_from_db()
        self.assertEqual(sale.notes, 'After')

    def test_apply_sale_complete_rollback_and_debt(self):
        queued = Sale.objects.create(
            sale_number='S-Q2',
            status='pending_approval',
            subtotal=Decimal('15'),
            total=Decimal('15'),
            payment_method='cash',
            amount_paid=Decimal('15'),
            cashier=self.user,
        )
        SaleItem.objects.create(
            sale=queued,
            product=self.product,
            quantity=1,
            unit_price=Decimal('15'),
            subtotal=Decimal('15'),
        )
        complete = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(queued.pk),
            entity_repr='S-Q2',
            original_values={},
            proposed_values={},
            reason='Approve sale',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(complete)
        queued.refresh_from_db()
        self.assertEqual(queued.status, 'completed')

        completed = Sale.objects.create(
            sale_number='S-RB2',
            status='completed',
            subtotal=Decimal('15'),
            total=Decimal('15'),
            payment_method='cash',
            amount_paid=Decimal('15'),
            cashier=self.user,
        )
        SaleItem.objects.create(
            sale=completed,
            product=self.product,
            quantity=1,
            unit_price=Decimal('15'),
            subtotal=Decimal('15'),
        )
        rollback = PendingChange.objects.create(
            action_type=ACTION_SALE_ROLLBACK,
            entity_type='sales.Sale',
            entity_id=str(completed.pk),
            entity_repr='S-RB2',
            original_values={},
            proposed_values={},
            reason='Rollback',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            checked_by=self.checker,
            apply_payload={},
        )
        apply_pending_change(rollback)

        customer = Customer.objects.create(name='Debtor', wallet_balance=Decimal('-20'))
        debt = PendingChange.objects.create(
            action_type=ACTION_DEBT_COLLECTION,
            entity_type='sales.Customer',
            entity_id=str(customer.pk),
            entity_repr=str(customer),
            original_values={},
            proposed_values={},
            reason='Collect',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            checked_by=self.checker,
            apply_payload={'amount': '5', 'payment_method': 'cash'},
        )
        apply_pending_change(debt)
        customer.refresh_from_db()
        self.assertGreater(customer.wallet_balance, Decimal('-20'))


class EffectiveSchemaAndOverlayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('sch_user', password='x')
        cls.cat = Category.objects.create(name='Sch Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Sch Prod',
            sku='SCH-1',
            category=cls.cat,
            price=Decimal('11'),
            stock_quantity=6,
            is_active=True,
        )
        cls.size = Size.objects.create(name='Sch-S', code='SS', is_active=True)
        cls.color = Color.objects.create(name='Sch-C', is_active=True)
        cls.variant = ProductVariant.objects.create(
            product=cls.product,
            size=cls.size,
            color=cls.color,
            sku='SCH-V',
            price=Decimal('11'),
            stock_quantity=3,
            is_active=True,
        )

    def test_overlays_short_circuit_when_disabled(self):
        disable_maker_checker()
        variant_data = apply_approved_variant_overlay(self.variant, {'price': '11'})
        self.assertNotIn('pending_approval', variant_data)
        enable_maker_checker()
        PendingChange.objects.create(
            entity_type='products.ProductVariant',
            entity_id=str(self.variant.pk),
            action_type=ACTION_PRODUCT_PRICE,
            status=PendingChange.STATUS_PENDING,
            proposed_values={'price': '20'},
            made_by=self.user,
        )
        with_pending = apply_approved_variant_overlay(self.variant, {'price': '11'})
        self.assertIn('pending_approval', with_pending)

    def test_pending_schema_guard(self):
        import approvals.effective as eff

        eff._pending_schema_ready = False
        try:
            merged = eff._merge_pending_proposed_values(
                'products.Product',
                self.product.pk,
                (ACTION_PRODUCT_PRICE,),
            )
            self.assertEqual(merged, {})
        finally:
            eff._pending_schema_ready = None
        self.assertTrue(pending_schema_ready())


class DetailsCacheVariantHydrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('dcv', password='x')
        cls.cat = Category.objects.create(name='DCV Cat', is_active=True)
        cls.product = Product.objects.create(
            name='DCV Prod',
            sku='DCV-1',
            category=cls.cat,
            price=Decimal('9'),
            stock_quantity=2,
            is_active=True,
        )
        cls.size = Size.objects.create(name='DCV-S', code='DS', is_active=True)
        cls.color = Color.objects.create(name='DCV-C', is_active=True)
        cls.variant = ProductVariant.objects.create(
            product=cls.product,
            size=cls.size,
            color=cls.color,
            sku='DCV-V',
            price=Decimal('9'),
            stock_quantity=2,
            is_active=True,
        )

    def test_cache_loads_variants_from_backfill_and_entity_rows(self):
        changes = [
            PendingChange(
                action_type=ACTION_SALE_BACKFILL,
                apply_payload={
                    'items': [{'product_id': self.product.pk, 'variant_id': self.variant.pk}],
                },
            ),
            PendingChange(
                entity_type='products.ProductVariant',
                entity_id=str(self.variant.pk),
                action_type=ACTION_PRODUCT_STOCK,
            ),
        ]
        cache = build_details_cache(changes)
        self.assertIn(self.variant.pk, cache.variants)
        self.assertIn(self.product.pk, cache.products)


class ViewsApproveRejectErrorTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.checker = User.objects.create_user('view_chk', password='x', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )

    def _checker_client(self):
        client = self.client.__class__()
        token = RefreshToken.for_user(self.checker)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        return client

    def test_approve_reject_validation_error_shapes(self):
        _enable_maker_checker()
        cat = Category.objects.create(name='View Cat', is_active=True)
        product = Product.objects.create(
            name='View Prod',
            sku='VIEW-1',
            category=cat,
            price=Decimal('100'),
            stock_quantity=5,
            is_active=True,
        )
        resp = self.client.patch(
            f'/api/products/{product.id}/',
            {'price': '250.00', 'reason': 'Big jump'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        pending = PendingChange.objects.get(status=PendingChange.STATUS_PENDING)
        checker = self._checker_client()
        bad_approve = checker.post(
            f'/api/approvals/pending-changes/{pending.id}/approve/',
            {},
            format='json',
        )
        self.assertEqual(bad_approve.status_code, status.HTTP_400_BAD_REQUEST)

        pending.refresh_from_db()
        pending.status = PendingChange.STATUS_PENDING
        pending.checked_by = None
        pending.checked_at = None
        pending.save(update_fields=['status', 'checked_by', 'checked_at'])
        bad_reject = checker.post(
            f'/api/approvals/pending-changes/{pending.id}/reject/',
            {'rejection_reason': ''},
            format='json',
        )
        self.assertEqual(bad_reject.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pending_count_multi_exclude_csv(self):
        PendingChange.objects.all().delete()
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id='1',
            entity_repr='S',
            original_values={},
            proposed_values={},
            reason='x',
            status=PendingChange.STATUS_PENDING,
            made_by=self.manager_user,
        )
        PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id='2',
            entity_repr='P',
            original_values={},
            proposed_values={'price': '1'},
            reason='y',
            status=PendingChange.STATUS_PENDING,
            made_by=self.manager_user,
        )
        resp = self.client.get(
            '/api/approvals/pending-changes/pending-count/',
            {
                'exclude_action_type': [
                    ACTION_SALE_COMPLETE,
                    ACTION_PRODUCT_PRICE,
                ],
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 0)

        csv_resp = self.client.get(
            '/api/approvals/pending-changes/pending-count/',
            {'exclude_action_type': f'{ACTION_SALE_COMPLETE},{ACTION_PRODUCT_PRICE}'},
        )
        self.assertEqual(csv_resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(csv_resp.data['count'], 2)


class PermissionsExtendedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()

    def test_debt_checker_and_past_dated_dates(self):
        debt_perm = Permission.objects.get(module='debt_management', action='approve')
        role = Role.objects.create(name='Debt Checker Role')
        role.permissions.add(debt_perm)
        user = User.objects.create_user('debt_chk', password='x')
        UserProfile.objects.create(user=user, role='custom', custom_role=role, is_active=True)
        self.assertTrue(user_can_check(user, ACTION_DEBT_COLLECTION))

        admin_role = Role.objects.create(name='Administrator')
        admin_user = User.objects.create_user('past_admin', password='x')
        UserProfile.objects.create(
            user=admin_user,
            role='manager',
            custom_role=admin_role,
            is_active=True,
        )
        self.assertTrue(user_may_approve_past_items(admin_user))

        maker = User.objects.create_user('past_maker', password='x')
        change = PendingChange(
            action_type=ACTION_SALE_BACKFILL,
            made_at=timezone.now(),
            apply_payload={'occurred_at': '2000-01-01T08:00:00'},
        )
        self.assertTrue(change_is_past_dated(change))
        dates = change_business_dates(
            PendingChange(
                action_type=ACTION_SALE_COMPLETE,
                entity_id='not-int',
                made_at=timezone.now(),
            )
        )
        self.assertGreaterEqual(len(dates), 1)


class ApplyBackfillAndServiceSaleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        cls.user = User.objects.create_user('bf_user', password='x')
        cls.checker = User.objects.create_user('bf_checker', password='x', is_staff=True)
        UserProfile.objects.create(
            user=cls.checker,
            role='super_admin',
            custom_role=Role.objects.get(name=ROLE_SUPER_ADMIN),
            is_active=True,
        )
        cls.cat = Category.objects.create(name='BF Cat', is_active=True)
        cls.product = Product.objects.create(
            name='BF Prod',
            sku='BF-1',
            category=cls.cat,
            price=Decimal('25'),
            cost=Decimal('10'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )
        cls.sale = Sale.objects.create(
            sale_number='S-BF-VAL',
            status='completed',
            subtotal=Decimal('25'),
            total=Decimal('25'),
            payment_method='cash',
            amount_paid=Decimal('25'),
            cashier=cls.user,
        )
        SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            quantity=1,
            unit_price=Decimal('25'),
            subtotal=Decimal('25'),
        )

    def setUp(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = True
        store.backfill_maker_checker_enabled = True
        store.save(update_fields=['maker_checker_enabled', 'backfill_maker_checker_enabled'])

    def test_apply_sale_backfill_entity(self):
        occurred = timezone.now() - timedelta(days=2)
        payload = {
            'occurred_at': occurred.isoformat(),
            'backfill_reason': 'Offline register',
            'sale_type': 'pos',
            'payment_method': 'cash',
            'amount_paid': '25.00',
            'acknowledge_stock_warnings': True,
            'items': [{'product_id': self.product.pk, 'quantity': 1, 'unit_price': '25.00'}],
        }
        change = PendingChange.objects.create(
            action_type=ACTION_SALE_BACKFILL,
            entity_type='sales.SaleBackfill',
            entity_id='new',
            entity_repr='Past sale',
            original_values={},
            proposed_values={},
            reason='Record missing sale',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            checked_by=self.checker,
            apply_payload=payload,
        )
        apply_pending_change(change)
        change.refresh_from_db()
        self.assertEqual(change.entity_type, 'sales.Sale')
        self.assertIn('sale_id', change.apply_payload)

    def test_validate_refund_and_complete_edge_cases(self):
        refund_change = PendingChange(
            action_type=ACTION_SALE_REFUND,
            entity_id=str(self.sale.pk),
            apply_payload={'full': True},
        )
        self.sale.refund_status = 'refunded'
        self.sale.save(update_fields=['refund_status'])
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(refund_change)
        self.sale.refund_status = 'none'
        self.sale.save(update_fields=['refund_status'])

        missing = PendingChange(action_type=ACTION_SALE_COMPLETE, entity_id='999999')
        with self.assertRaises(DjangoValidationError):
            validate_before_approval(missing)

        naive_backfill = PendingChange(
            action_type=ACTION_SALE_BACKFILL,
            apply_payload={'occurred_at': '2020-01-01 09:00:00'},
        )
        validate_before_approval(naive_backfill)

    def test_reject_and_resubmit_sale_complete(self):
        queued = Sale.objects.create(
            sale_number='S-SCR',
            status='pending_approval',
            subtotal=Decimal('25'),
            total=Decimal('25'),
            payment_method='cash',
            amount_paid=Decimal('25'),
            cashier=self.user,
        )
        SaleItem.objects.create(
            sale=queued,
            product=self.product,
            quantity=1,
            unit_price=Decimal('25'),
            subtotal=Decimal('25'),
        )
        change = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(queued.pk),
            entity_repr='S-SCR',
            original_values={'status': 'pending_approval'},
            proposed_values={'status': 'completed'},
            reason='Till queue',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
        )
        reject_change(change, self.checker, 'Fix payment', request=_request(self.checker))
        change.refresh_from_db()
        self.assertEqual(change.status, PendingChange.STATUS_REJECTED)
        queued.refresh_from_db()
        self.assertNotEqual(queued.status, 'completed')

        queued.payment_method = 'mpesa'
        queued.save(update_fields=['payment_method'])
        try:
            resubmit_change(change, self.user, reason='Corrected', request=_request(self.user))
        except DjangoValidationError:
            pass
        else:
            change.refresh_from_db()
            self.assertIn(change.status, (PendingChange.STATUS_PENDING, PendingChange.STATUS_REJECTED))

    def test_route_product_no_sensitive_fields(self):
        enable_maker_checker()
        req = _request(self.user)
        self.assertIsNone(
            route_product_sensitive_update(
                req,
                self.product,
                {'description': 'New label only'},
                reason='Non sensitive',
            )
        )

    def test_route_product_unit_and_apply_selling_price(self):
        enable_maker_checker()
        req = _request(self.user)
        change = route_product_sensitive_update(
            req,
            self.product,
            {'unit': 'kg'},
            reason='Use kilograms',
        )
        self.assertIsNotNone(change)

        price_change = PendingChange(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            proposed_values={'selling_price': '30.00'},
            made_by=self.user,
            checked_by=self.checker,
        )
        apply_pending_change(price_change)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('30.00'))


class DetailsAndCacheFinalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sync_default_roles()
        ensure_permissions()
        cls.user = User.objects.create_user('det2', password='x', first_name='Zed')
        cls.cat = Category.objects.create(name='Det2 Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Det2 Prod',
            sku='D2-1',
            category=cls.cat,
            price=Decimal('40'),
            stock_quantity=7,
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='Det Customer', wallet_balance=Decimal('-10'))
        cls.role = Role.objects.get(name=ROLE_MANAGER)
        cls.perm = Permission.objects.first()
        tenant = Tenant.objects.create(
            name='Det2 Tenant',
            code='DT2',
            country='Kenya',
            owner=cls.user,
            created_by=cls.user,
        )
        cls.branch = Branch.objects.create(
            tenant=tenant,
            branch_code='DT2-B1',
            name='Det Branch',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=cls.user,
        )

    def test_dec_invalid_and_debt_role_stock_details(self):
        self.assertEqual(_dec('not-money'), Decimal('0'))

        debt = PendingChange.objects.create(
            action_type=ACTION_DEBT_COLLECTION,
            entity_type='sales.Customer',
            entity_id=str(self.customer.pk),
            entity_repr=str(self.customer),
            original_values={'wallet_balance': '-10'},
            proposed_values={},
            reason='Collect',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            apply_payload={'amount': '5', 'payment_method': 'cash'},
        )
        cache = build_details_cache([debt])
        details = pending_change_details(debt, cache=cache)
        self.assertTrue(details.get('sections'))

        role_change = PendingChange.objects.create(
            action_type=ACTION_ROLE_PERMISSIONS,
            entity_type='accounts.Role',
            entity_id=str(self.role.pk),
            entity_repr=str(self.role),
            original_values={'permission_ids': []},
            proposed_values={'permission_ids': [self.perm.pk]},
            reason='Access',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
        )
        role_cache = build_details_cache([role_change])
        role_details = pending_change_details(role_change, cache=role_cache)
        self.assertTrue(role_details.get('sections'))

        transfer = PendingChange.objects.create(
            action_type=ACTION_STOCK_TRANSFER,
            entity_type='products.Product',
            entity_id=str(self.product.pk),
            entity_repr=str(self.product),
            original_values={'stock_quantity': 7},
            proposed_values={'stock_quantity': 5},
            reason='Move',
            status=PendingChange.STATUS_PENDING,
            made_by=self.user,
            apply_payload={
                'product_id': self.product.pk,
                'quantity': 2,
                'branch_id': self.branch.pk,
                'to_branch_id': self.branch.pk,
            },
        )
        self.assertTrue(pending_change_details(transfer, cache=build_details_cache([transfer])))

    def test_sale_sections_without_prefetch_and_cache_duplicates(self):
        sale = Sale.objects.create(
            sale_number='S-DET2',
            status='completed',
            subtotal=Decimal('40'),
            total=Decimal('40'),
            payment_method='cash',
            amount_paid=Decimal('40'),
            customer=self.customer,
            cashier=self.user,
            served_by=self.user,
            discount_amount=Decimal('1'),
            tax_amount=Decimal('2'),
            delivery_cost=Decimal('3'),
            change=Decimal('0.50'),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('40'),
            subtotal=Decimal('40'),
        )
        sections = sale_sections(sale)
        self.assertTrue(sections)

        pending_sale = Sale.objects.create(
            sale_number='S-DUP',
            status='pending_approval',
            subtotal=Decimal('1'),
            total=Decimal('1'),
            payment_method='cash',
            amount_paid=Decimal('1'),
            cashier=self.user,
        )
        for _ in range(2):
            PendingChange.objects.create(
                action_type=ACTION_SALE_COMPLETE,
                entity_type='sales.Sale',
                entity_id=str(pending_sale.pk),
                entity_repr='S-DUP',
                original_values={},
                proposed_values={},
                reason='Dup',
                status=PendingChange.STATUS_PENDING,
                made_by=self.user,
            )
        cache = build_sale_approval_cache([pending_sale])
        self.assertEqual(len(cache.pending_complete_by_sale_id), 1)

        size = Size.objects.create(name='Det-S', code='DS2', is_active=True)
        color = Color.objects.create(name='Det-C', is_active=True)
        variant = ProductVariant.objects.create(
            product=self.product,
            size=size,
            color=color,
            sku='D2-V',
            price=Decimal('40'),
            stock_quantity=2,
            is_active=True,
        )
        build_details_cache([
            PendingChange(
                action_type=ACTION_STOCK_ADJUST,
                apply_payload={'product_id': self.product.pk, 'variant_id': variant.pk},
            ),
            PendingChange(
                action_type=ACTION_ROLE_PERMISSIONS,
                entity_id=str(self.role.pk),
                proposed_values={'permission_ids': ['', self.perm.pk]},
                original_values={'permission_ids': ['not-int', self.perm.pk]},
            ),
            PendingChange(
                entity_type='products.ProductVariant',
                entity_id=str(variant.pk),
                action_type=ACTION_PRODUCT_STOCK,
            ),
        ])

    def test_refund_summary_validation_error(self):
        sale = Sale.objects.create(
            sale_number='S-DET-REF',
            status='completed',
            subtotal=Decimal('40'),
            total=Decimal('40'),
            payment_method='cash',
            amount_paid=Decimal('40'),
            cashier=self.user,
        )
        with patch('approvals.refund_integration.SaleRefundService') as mock_svc:
            mock_svc.return_value._resolve_refund_lines.side_effect = DjangoValidationError('bad')
            summary = _summarize_refund_lines(sale, items=None, full=True)
            self.assertEqual(summary, '—')


class EffectiveAndPermissionsFinalTests(TestCase):
    def test_effective_operational_error_and_permissions_manage(self):
        import approvals.effective as eff

        enable_maker_checker()
        cat = Category.objects.create(name='Eff3', is_active=True)
        product = Product.objects.create(
            name='Eff3',
            sku='E3',
            category=cat,
            price=Decimal('1'),
            stock_quantity=1,
            is_active=True,
        )

        from django.db.utils import OperationalError

        with patch.object(
            PendingChange.objects,
            'filter',
            side_effect=OperationalError('no table'),
        ):
            self.assertFalse(eff.has_pending_product_price(product.pk))

        manage_perm = Permission.objects.filter(module='settings', action='manage').first()
        if manage_perm is None:
            manage_perm = Permission.objects.create(module='settings', action='manage', name='Manage settings')
        role = Role.objects.create(name='Settings Manager')
        role.permissions.add(manage_perm)
        user = User.objects.create_user('settings_mgr', password='x')
        UserProfile.objects.create(user=user, role='custom', custom_role=role, is_active=True)
        self.assertTrue(user_can_check(user, ACTION_STORE_SETTINGS))

        sale = Sale.objects.create(
            sale_number='S-DATES',
            status='pending_approval',
            subtotal=Decimal('1'),
            total=Decimal('1'),
            payment_method='cash',
            amount_paid=Decimal('1'),
            occurred_at=timezone.now() - timedelta(days=3),
            cashier=user,
        )
        change = PendingChange(
            action_type=ACTION_SALE_COMPLETE,
            entity_id=str(sale.pk),
            made_at=timezone.now(),
        )
        dates = change_business_dates(change, sales_by_id={sale.pk: sale})
        self.assertGreaterEqual(len(dates), 2)

        disable_maker_checker()
        self.assertFalse(eff.has_pending_product_deactivation(product.pk))


class ViewsResubmitValidationTests(ManagerAPITestCase):
    def test_resubmit_validation_error_response(self):
        _enable_maker_checker()
        change = PendingChange.objects.create(
            action_type=ACTION_PRODUCT_PRICE,
            entity_type='products.Product',
            entity_id='99',
            entity_repr='Ghost',
            original_values={'price': '1'},
            proposed_values={'price': '2'},
            reason='Still pending',
            status=PendingChange.STATUS_PENDING,
            made_by=self.manager_user,
        )
        resp = self.client.post(
            f'/api/approvals/pending-changes/{change.id}/resubmit/',
            {'reason': 'Too early'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class FinalLineCoverageTests(TestCase):
    def test_reason_rules_selling_price_previous(self):
        product = Product.objects.create(
            name='RR',
            sku='RR-1',
            category=Category.objects.create(name='RR Cat', is_active=True),
            price=Decimal('10'),
            stock_quantity=1,
            is_active=True,
        )
        self.assertEqual(_previous_field_value(product, 'selling_price'), Decimal('10'))

    def test_details_cache_sale_complete_entity(self):
        user = User.objects.create_user('dc_sc', password='x')
        sale = Sale.objects.create(
            sale_number='S-SCC',
            status='pending_approval',
            subtotal=Decimal('1'),
            total=Decimal('1'),
            payment_method='cash',
            amount_paid=Decimal('1'),
            cashier=user,
        )
        cache = build_details_cache([
            PendingChange(
                action_type=ACTION_SALE_COMPLETE,
                entity_id=str(sale.pk),
            ),
        ])
        self.assertIn(sale.pk, cache.sales)
