"""Sale tender normalize / label helpers (pay later ≠ cash)."""

from decimal import Decimal

from django.test import SimpleTestCase

from sales.sale_payment_method import (
    normalize_sale_payment_method,
    sale_payment_method_label,
)


class SalePaymentMethodTests(SimpleTestCase):
    def test_normalize_pay_later_to_on_account(self):
        self.assertEqual(
            normalize_sale_payment_method(
                payment_method='cash',
                amount_paid=0,
                allow_partial=True,
            ),
            'on_account',
        )
        self.assertEqual(
            normalize_sale_payment_method(
                payment_method='mpesa',
                amount_paid=Decimal('10.00'),
                allow_partial=False,
            ),
            'mpesa',
        )

    def test_label_never_cash_when_unpaid(self):
        self.assertEqual(
            sale_payment_method_label(
                'cash',
                amount_paid=0,
                total=500,
            ),
            'Pay later',
        )
        self.assertEqual(
            sale_payment_method_label('on_account', amount_paid=0, total=100),
            'Pay later',
        )

    def test_label_mpesa_till_bank(self):
        self.assertEqual(
            sale_payment_method_label(
                'mpesa',
                amount_paid=100,
                total=100,
                mpesa_destination='till',
            ),
            'M-Pesa · Till',
        )
        self.assertEqual(
            sale_payment_method_label(
                'mpesa',
                amount_paid=100,
                total=100,
                mpesa_destination='bank',
            ),
            'M-Pesa · Bank',
        )
        self.assertEqual(
            sale_payment_method_label('cash', amount_paid=100, total=100),
            'Cash',
        )
