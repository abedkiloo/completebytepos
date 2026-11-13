"""Sale tender normalize / label helpers (debt ≠ cash; repaid ≠ on account)."""

from decimal import Decimal

from django.test import SimpleTestCase

from sales.sale_payment_method import (
    normalize_sale_payment_method,
    sale_payment_method_label,
)


class SalePaymentMethodUnitTests(SimpleTestCase):
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

    def test_label_debt_never_cash_when_unpaid(self):
        self.assertEqual(
            sale_payment_method_label(
                'cash',
                amount_paid=0,
                total=500,
            ),
            'Debt',
        )
        self.assertEqual(
            sale_payment_method_label('on_account', amount_paid=0, total=100),
            'Debt',
        )

    def test_corrected_debt_repaid_when_settled(self):
        self.assertEqual(
            sale_payment_method_label(
                'on_account',
                amount_paid=Decimal('100.00'),
                total=Decimal('100.00'),
            ),
            'Debt repaid',
        )
        self.assertEqual(
            sale_payment_method_label(
                'on_account',
                amount_paid=Decimal('40.00'),
                total=Decimal('100.00'),
            ),
            'Debt',
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


class SalePaymentMethodStressTests(SimpleTestCase):
    def test_label_stress_batch(self):
        for i in range(500):
            unpaid = sale_payment_method_label(
                'on_account',
                amount_paid=0,
                total=100 + (i % 20),
            )
            self.assertEqual(unpaid, 'Debt')
            repaid = sale_payment_method_label(
                'on_account',
                amount_paid=100 + (i % 20),
                total=100 + (i % 20),
            )
            self.assertEqual(repaid, 'Debt repaid')


class SalePaymentMethodSecurityTests(SimpleTestCase):
    def test_label_never_exposes_on_account_wording(self):
        for method, paid, total in (
            ('on_account', 0, 50),
            ('on_account', 50, 50),
            ('cash', 0, 50),
        ):
            label = sale_payment_method_label(method, amount_paid=paid, total=total)
            self.assertNotIn('on account', label.lower())
            self.assertNotIn('pay later', label.lower())
            self.assertNotEqual(label.lower(), 'cash')
