"""Posted sale corrections require Admin / Super Admin validation — not managers."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from accounts.models import UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from approvals.models import PendingChange
from approvals.permissions import (
    POSTED_CORRECTION_ADMIN_ONLY_MESSAGE,
    change_is_posted_sale_correction,
    user_may_approve_change,
)
from approvals.registry import ACTION_SALE_COMPLETE
from approvals.serializers import PendingChangeSerializer
from approvals.service import approve_change, reject_change
from sales.models import Sale
from sales.sale_completion_approval import QUEUE_REASON
from settings.test_utils import disable_maker_checker


class PostedCorrectionAdminGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        disable_maker_checker()
        cls.manager = User.objects.create_user('corr_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.admin = User.objects.create_user('corr_admin', password='x')
        UserProfile.objects.create(
            user=cls.admin,
            role='super_admin',
            custom_role=roles[ROLE_SUPER_ADMIN],
            is_active=True,
        )
        cls.sales = User.objects.create_user('corr_sales', password='x')
        UserProfile.objects.create(
            user=cls.sales, role='cashier', custom_role=roles[ROLE_SALES], is_active=True,
        )

    def _posted_correction_change(self):
        sale = Sale.objects.create(
            sale_number='S-POSTED-CORR',
            status='pending_approval',
            cashier=self.sales,
            subtotal=Decimal('100'),
            total=Decimal('100'),
            payment_method='cash',
            amount_paid=Decimal('0'),
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            reason='Wrong payment — was not paid',
            status=PendingChange.STATUS_REJECTED,
            made_by=self.admin,
            original_values={
                'status': 'completed',
                'returned_from_status': 'completed',
            },
            apply_payload={},
        )
        change = PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            reason=QUEUE_REASON,
            status=PendingChange.STATUS_PENDING,
            made_by=self.sales,
            original_values={
                'status': 'holding',
                'returned_from_status': 'completed',
            },
            apply_payload={'amount_paid': '0', 'allow_partial': True},
        )
        return sale, change

    def test_manager_cannot_approve_or_return_posted_correction(self):
        sale, change = self._posted_correction_change()
        self.assertTrue(change_is_posted_sale_correction(change))
        self.assertFalse(user_may_approve_change(self.manager, change))
        self.assertTrue(user_may_approve_change(self.admin, change))
        self.assertTrue(PendingChangeSerializer(change).data['posted_correction'])

        with self.assertRaises(DjangoValidationError) as ctx:
            reject_change(change, self.manager, 'looks fine')
        self.assertIn(POSTED_CORRECTION_ADMIN_ONLY_MESSAGE, str(ctx.exception))
        change.refresh_from_db()
        self.assertEqual(change.status, PendingChange.STATUS_PENDING)

        with self.assertRaises(DjangoValidationError) as ctx:
            approve_change(change, self.manager)
        self.assertIn(POSTED_CORRECTION_ADMIN_ONLY_MESSAGE, str(ctx.exception))
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'pending_approval')
