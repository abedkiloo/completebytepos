"""Messaging owed_amount helper coverage."""

from decimal import Decimal

from django.test import SimpleTestCase

from messaging.services import owed_amount
from sales.models import Customer


class OwedAmountTests(SimpleTestCase):
    def test_owed_amount(self):
        c = Customer(name='x', wallet_balance=Decimal('-12.5'))
        self.assertEqual(owed_amount(c), Decimal('12.5'))
        c2 = Customer(name='y', wallet_balance=Decimal('3'))
        self.assertEqual(owed_amount(c2), Decimal('0'))
        c3 = Customer(name='z', wallet_balance=None)
        self.assertEqual(owed_amount(c3), Decimal('0'))
