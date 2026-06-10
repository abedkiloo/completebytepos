from decimal import Decimal

from django.test import SimpleTestCase

from approvals.reason_rules import (
    is_initial_sensitive_set,
    is_unset_financial_value,
    split_initial_vs_change_sensitive,
)


class _FakeProduct:
    price = Decimal('0')
    stock_quantity = 0
    is_active = True


class ReasonRulesTests(SimpleTestCase):
    def test_unset_financial_values(self):
        self.assertTrue(is_unset_financial_value(None))
        self.assertTrue(is_unset_financial_value(''))
        self.assertTrue(is_unset_financial_value(0))
        self.assertTrue(is_unset_financial_value('0'))
        self.assertFalse(is_unset_financial_value('10'))

    def test_initial_price_set_not_a_change(self):
        self.assertTrue(is_initial_sensitive_set('price', Decimal('0'), Decimal('80')))
        self.assertFalse(is_initial_sensitive_set('price', Decimal('50'), Decimal('80')))
        self.assertFalse(is_initial_sensitive_set('is_active', True, False))

    def test_split_initial_vs_change(self):
        product = _FakeProduct()
        initial, change = split_initial_vs_change_sensitive(
            product,
            {'price': Decimal('99'), 'stock_quantity': 5},
        )
        self.assertEqual(initial, {'price': Decimal('99'), 'stock_quantity': 5})
        self.assertEqual(change, {})

        product.price = Decimal('50')
        initial, change = split_initial_vs_change_sensitive(
            product,
            {'price': Decimal('80')},
        )
        self.assertEqual(initial, {})
        self.assertEqual(change, {'price': Decimal('80')})

    def test_unchanged_sensitive_fields_are_ignored(self):
        product = _FakeProduct()
        product.price = Decimal('30')
        product.stock_quantity = 0
        product.is_active = True
        initial, change = split_initial_vs_change_sensitive(
            product,
            {
                'price': Decimal('30.00'),
                'stock_quantity': 0,
                'is_active': True,
                'track_stock': True,
            },
        )
        self.assertEqual(initial, {})
        self.assertEqual(change, {})
