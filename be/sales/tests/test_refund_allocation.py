from decimal import Decimal
from django.test import TestCase

from sales.models import Sale
from sales.refund_allocation import compute_refund_allocation


class RefundAllocationTests(TestCase):
    def test_pay_later_sale_allocates_to_debt(self):
        sale = Sale(
            total=Decimal('100'),
            amount_paid=Decimal('0'),
        )
        allocation = compute_refund_allocation(sale, Decimal('100'))
        self.assertEqual(allocation['cash_back'], Decimal('0'))
        self.assertEqual(allocation['debt_back'], Decimal('100'))

    def test_mixed_payment_splits_refund(self):
        sale = Sale(
            total=Decimal('100'),
            amount_paid=Decimal('30'),
        )
        allocation = compute_refund_allocation(sale, Decimal('100'))
        self.assertEqual(allocation['cash_back'], Decimal('30'))
        self.assertEqual(allocation['debt_back'], Decimal('70'))
