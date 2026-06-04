"""Invoice line payload normalization."""

from django.test import SimpleTestCase

from sales.invoice_items import normalize_invoice_items, resolve_product_id


class ResolveProductIdTests(SimpleTestCase):
    def test_prefers_product_id(self):
        self.assertEqual(resolve_product_id({'product_id': 5, 'product': 9}), 5)

    def test_accepts_product_alias(self):
        self.assertEqual(resolve_product_id({'product': '12'}), 12)

    def test_returns_none_when_missing(self):
        self.assertIsNone(resolve_product_id({}))
        self.assertIsNone(resolve_product_id({'product_id': ''}))


class NormalizeInvoiceItemsTests(SimpleTestCase):
    def test_sets_product_id_from_product(self):
        rows = normalize_invoice_items(
            [{'product': 3, 'quantity': 2, 'unit_price': '10'}]
        )
        self.assertEqual(rows[0]['product_id'], 3)

    def test_skips_non_dict_rows(self):
        self.assertEqual(normalize_invoice_items([None, 'x']), [])
