from django.test import SimpleTestCase

from utils.money_format import format_grouped_number, format_kes


class MoneyFormatTests(SimpleTestCase):
    def test_format_grouped_number(self):
        self.assertEqual(format_grouped_number(1000, decimals=None), '1,000')
        self.assertEqual(format_grouped_number('1000.50', decimals=None), '1,000.5')
        self.assertEqual(format_grouped_number(1234567.8, decimals=2), '1,234,567.80')
        self.assertEqual(format_grouped_number(1500, decimals=0), '1,500')
        self.assertEqual(format_grouped_number(None, decimals=None), '0')
        self.assertEqual(format_grouped_number('not-a-number', decimals=2), '0.00')
        self.assertEqual(format_grouped_number(10.00, decimals=None), '10')
        self.assertEqual(format_grouped_number(1.2500, decimals=None), '1.25')
        # Non-integral that rounds to .00 (hits strip-.00 branch)
        self.assertEqual(format_grouped_number('1.001', decimals=None), '1')
        self.assertEqual(format_kes(1000, decimals=None), 'KES 1,000')
        self.assertEqual(format_kes(2500.5, decimals=None), 'KES 2,500.5')
        self.assertEqual(format_kes(1000), 'KES 1,000.00')
