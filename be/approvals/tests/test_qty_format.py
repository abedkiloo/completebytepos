from decimal import Decimal

from django.test import SimpleTestCase

from approvals.details import _format_qty, _line


class ApprovalQtyFormatTests(SimpleTestCase):
    def test_integral_qty_never_scientific(self):
        self.assertEqual(_format_qty(Decimal('10')), '10')
        self.assertEqual(_format_qty(Decimal('1E+1')), '10')
        self.assertEqual(_format_qty(Decimal('1000')), '1000')
        self.assertEqual(_line('Pins', '', Decimal('10'), '430', '4300')['quantity'], '10')

    def test_fractional_qty_plain(self):
        self.assertEqual(_format_qty(Decimal('1.5')), '1.5')
        self.assertEqual(_format_qty(Decimal('2.50')), '2.5')
