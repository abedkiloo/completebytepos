"""Checkout must stamp the business sale day — not the cart-open day."""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_SALES, sync_default_roles
from approvals.models import PendingChange
from approvals.registry import ACTION_SALE_COMPLETE
from products.models import Category, Product
from sales.activity import build_sale_activity
from sales.models import Sale, SaleItem
from sales.sale_date import stamp_occurred_at_for_pos_checkout
from sales.services import SaleService
from utils.tests.api_test_base import ManagerAPITestCase


class SaleOccurredAtCheckoutTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_default_roles()
        cls.cashier = User.objects.create_user('date_cashier', password='x')
        UserProfile.objects.create(
            user=cls.cashier,
            role='cashier',
            custom_role=Role.objects.get(name=ROLE_SALES),
            is_active=True,
        )
        cls.cat = Category.objects.create(name='DateCat', is_active=True)
        cls.product = Product.objects.create(
            name='Date Item',
            sku='DATE-1',
            category=cls.cat,
            price=Decimal('100'),
            cost=Decimal('40'),
            stock_quantity=50,
            track_stock=True,
            is_active=True,
        )

    def _holding(self, *, occurred_at, entry_source='pos'):
        sale = Sale.objects.create(
            sale_number='S-DATE-HOLD',
            status='holding',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            payment_method='cash',
            amount_paid=Decimal('0'),
            cashier=self.cashier,
            entry_source=entry_source,
            occurred_at=occurred_at,
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100'),
            subtotal=Decimal('100'),
        )
        return sale

    def test_stale_holding_checkout_stamps_today_not_cart_open_day(self):
        stale = timezone.now() - timedelta(days=18)
        holding = self._holding(occurred_at=stale)
        self.assertEqual(timezone.localtime(holding.occurred_at).date(), timezone.localtime(stale).date())

        before = timezone.now()
        SaleService().complete_holding_sale(
            holding,
            payment_method='cash',
            amount_paid=Decimal('100'),
            user=self.manager_user,
            allow_partial=False,
        )
        holding.refresh_from_db()
        self.assertEqual(holding.status, 'completed')
        self.assertGreaterEqual(holding.occurred_at, before)
        self.assertEqual(
            timezone.localtime(holding.occurred_at).date(),
            timezone.localdate(),
        )

    def test_backfill_checkout_does_not_restamp_occurred_at(self):
        past = timezone.now() - timedelta(days=10)
        holding = self._holding(occurred_at=past, entry_source='backfill')
        stamped = stamp_occurred_at_for_pos_checkout(holding)
        self.assertFalse(stamped)
        self.assertEqual(holding.occurred_at, past)

    def test_returned_from_completed_preserves_original_business_day(self):
        original = timezone.now() - timedelta(days=18)
        holding = self._holding(occurred_at=original)
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(holding.pk),
            entity_repr=holding.sale_number,
            original_values={'returned_from_status': 'completed'},
            proposed_values={},
            reason='fix items',
            status=PendingChange.STATUS_REJECTED,
            made_by=self.cashier,
            checked_by=self.manager_user,
            checked_at=timezone.now(),
            rejection_reason='Wrong qty',
        )
        stamped = stamp_occurred_at_for_pos_checkout(holding)
        self.assertFalse(stamped)
        self.assertEqual(holding.occurred_at, original)

        with mock.patch(
            'sales.sale_completion_approval.assert_returned_sale_was_edited',
            return_value=None,
        ):
            SaleService().complete_holding_sale(
                holding,
                payment_method='cash',
                amount_paid=Decimal('100'),
                user=self.manager_user,
                allow_partial=False,
                confirm_unchanged=True,
            )
        holding.refresh_from_db()
        self.assertEqual(
            timezone.localtime(holding.occurred_at).date(),
            timezone.localtime(original).date(),
        )

    def test_activity_separates_business_date_from_return_time(self):
        business = timezone.now() - timedelta(days=18)
        sale = Sale.objects.create(
            sale_number='S-DATE-ACT',
            status='holding',
            subtotal=Decimal('100'),
            total=Decimal('100'),
            payment_method='cash',
            amount_paid=Decimal('100'),
            cashier=self.cashier,
            occurred_at=business,
        )
        PendingChange.objects.create(
            action_type=ACTION_SALE_COMPLETE,
            entity_type='sales.Sale',
            entity_id=str(sale.pk),
            entity_repr=sale.sale_number,
            original_values={'returned_from_status': 'completed'},
            proposed_values={},
            reason='Fix',
            status=PendingChange.STATUS_REJECTED,
            made_by=self.cashier,
            checked_by=self.manager_user,
            checked_at=timezone.now(),
            rejection_reason='Wrong item',
        )
        events = build_sale_activity(sale)
        recorded = next(e for e in events if e['kind'] == 'recorded')
        rejected = next(e for e in events if e['kind'] == 'rejected')
        self.assertIn('Business sale date', recorded['detail'])
        self.assertIn('not a new sale day', rejected['detail'])
        self.assertIn(timezone.localtime(business).strftime('%Y'), recorded['detail'] or '')
