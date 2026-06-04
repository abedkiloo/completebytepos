"""Unit tests for optional P3 sales policy helpers."""

from django.test import TestCase

from approvals.sales_integration import queue_completed_sale_edit
from approvals.sales_policy import (
    COMPLETED_SALE_IMMUTABLE_MESSAGE,
    completed_sale_direct_edit_blocked,
    filter_queueable_sale_fields,
    is_sales_maker_checker_active,
)
from approvals.tests.test_maker_checker import _enable_maker_checker
from sales.models import Sale
from settings.models import StoreSettings


class SalesPolicyUnitTests(TestCase):
    def test_defaults_block_optional_mode(self):
        store = StoreSettings.load()
        store.maker_checker_enabled = False
        store.maker_checker_sales_controls = False
        store.save(
            update_fields=['maker_checker_enabled', 'maker_checker_sales_controls']
        )
        self.assertFalse(is_sales_maker_checker_active(store))
        self.assertTrue(completed_sale_direct_edit_blocked(store))
        self.assertIn('cannot be edited', COMPLETED_SALE_IMMUTABLE_MESSAGE.lower())

    def test_filter_queueable_fields(self):
        self.assertEqual(
            filter_queueable_sale_fields({'notes': 'x', 'total': 1}),
            {'notes': 'x'},
        )

    def test_queue_requires_optional_flag(self):
        _enable_maker_checker(enabled=True)
        store = StoreSettings.load()
        store.maker_checker_sales_controls = False
        store.save(update_fields=['maker_checker_sales_controls'])
        sale = Sale.objects.create(
            sale_number='POL-1',
            total=10,
            subtotal=10,
            status='completed',
            payment_method='cash',
            amount_paid=10,
        )
        from unittest.mock import Mock

        req = Mock(user=None, data={}, META={})
        with self.assertRaises(Exception):
            queue_completed_sale_edit(req, sale, {'notes': 'n'}, reason='r')
