"""Package feature gates: location filters, late SMS, history export helpers."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from messaging.customer_notify import notify_customer_sale_completed
from products.models import Category, Product
from sales.customer_location_filters import apply_customer_location_filters
from sales.customer_module_settings import customers_location_filters_enabled
from sales.models import Customer, Sale, SaleItem
from sales.module_settings import (
    sales_history_export_enabled,
    sales_late_sale_sms_enabled,
    sales_payments_trail_export_enabled,
)
from settings.models import ModuleFeature, ModuleSettings
from utils.tests.api_test_base import ManagerAPITestCase


def _set_feature(module_name: str, feature_key: str, enabled: bool) -> None:
    module, _ = ModuleSettings.objects.get_or_create(
        module_name=module_name,
        defaults={'is_enabled': True},
    )
    module.is_enabled = True
    module.save(update_fields=['is_enabled'])
    feat, _ = ModuleFeature.objects.get_or_create(
        module=module,
        feature_key=feature_key,
        defaults={'feature_name': feature_key, 'is_enabled': enabled},
    )
    feat.is_enabled = enabled
    feat.save(update_fields=['is_enabled'])


class PackageFeatureGateTests(ManagerAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.customer = Customer.objects.create(
            name='Gate Customer',
            phone='0700111222',
            county='Nairobi',
            sub_county='Westlands',
            ward='Parklands/Highridge',
        )
        cat = Category.objects.create(name='Gate Cat', is_active=True)
        cls.product = Product.objects.create(
            name='Gate Item',
            sku='GATE-1',
            category=cat,
            price=Decimal('50'),
            cost=Decimal('20'),
            stock_quantity=10,
            is_active=True,
        )

    def test_location_filters_noop_when_feature_off(self):
        _set_feature('customers', 'location_filters', False)
        self.assertFalse(customers_location_filters_enabled())
        qs = Customer.objects.all()
        filtered = apply_customer_location_filters(qs, {'county': 'Nairobi'})
        self.assertEqual(filtered.count(), qs.count())

        _set_feature('customers', 'location_filters', True)
        self.assertTrue(customers_location_filters_enabled())
        narrowed = apply_customer_location_filters(qs, {'county': 'Nairobi'})
        self.assertGreaterEqual(narrowed.count(), 1)

    def test_late_sale_sms_blocked_when_feature_off(self):
        _set_feature('sales', 'late_sale_sms', False)
        self.assertFalse(sales_late_sale_sms_enabled())
        sale = Sale.objects.create(
            sale_number='S-LATE-1',
            status='completed',
            entry_source='backfill',
            subtotal=Decimal('50'),
            total=Decimal('50'),
            amount_paid=Decimal('50'),
            payment_method='cash',
            cashier=self.manager_user,
            customer=self.customer,
            occurred_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            quantity=1,
            unit_price=Decimal('50'),
            unit_cost=Decimal('20'),
            subtotal=Decimal('50'),
        )
        self.assertIsNone(
            notify_customer_sale_completed(sale, force_late_entry=True)
        )

        _set_feature('sales', 'late_sale_sms', True)
        self.assertTrue(sales_late_sale_sms_enabled())

    def test_history_export_helper(self):
        _set_feature('sales', 'history_export', True)
        self.assertTrue(sales_history_export_enabled())
        _set_feature('sales', 'history_export', False)
        self.assertFalse(sales_history_export_enabled())

    def test_payments_trail_export_helper(self):
        _set_feature('sales', 'payments_trail_export', True)
        self.assertTrue(sales_payments_trail_export_enabled())
        _set_feature('sales', 'payments_trail_export', False)
        self.assertFalse(sales_payments_trail_export_enabled())

    def test_location_filter_sub_and_ward_without_county(self):
        from sales.kenya_admin import DEFAULT_COUNTY, DEFAULT_SUB_COUNTY, DEFAULT_WARD

        _set_feature('customers', 'location_filters', True)
        Customer.objects.create(
            name='SubOnly Match',
            phone='0700999001',
            county=DEFAULT_COUNTY,
            sub_county=DEFAULT_SUB_COUNTY,
            ward=DEFAULT_WARD,
        )
        qs = Customer.objects.all()
        by_sub = apply_customer_location_filters(qs, {'sub_county': DEFAULT_SUB_COUNTY})
        self.assertGreaterEqual(by_sub.count(), 1)
        by_ward = apply_customer_location_filters(qs, {'ward': DEFAULT_WARD})
        self.assertGreaterEqual(by_ward.count(), 1)
        self.assertEqual(
            apply_customer_location_filters(qs, {'sub_county': 'NoSuchSubXYZ'}).count(),
            0,
        )
        self.assertEqual(
            apply_customer_location_filters(qs, {'ward': 'NoSuchWardXYZ'}).count(),
            0,
        )
        self.assertEqual(
            apply_customer_location_filters(
                qs, {'county': DEFAULT_COUNTY, 'sub_county': 'NoSuchSubXYZ'}
            ).count(),
            0,
        )
        self.assertEqual(
            apply_customer_location_filters(
                qs,
                {
                    'county': DEFAULT_COUNTY,
                    'sub_county': DEFAULT_SUB_COUNTY,
                    'ward': 'NoSuchWardXYZ',
                },
            ).count(),
            0,
        )
        # County + ward without sub still resolves via catalog scan.
        with_county_ward = apply_customer_location_filters(
            qs, {'county': DEFAULT_COUNTY, 'ward': DEFAULT_WARD}
        )
        self.assertGreaterEqual(with_county_ward.count(), 1)
