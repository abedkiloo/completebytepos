from django.test import SimpleTestCase

from sales.item_consolidation import consolidate_sale_items_data


class ConsolidateSaleItemsTests(SimpleTestCase):
    def test_merges_duplicate_product_variant_rows(self):
        merged = consolidate_sale_items_data(
            [
                {'product_id': 5, 'variant_id': 12, 'quantity': 2, 'unit_price': '100'},
                {'product_id': 5, 'variant_id': 12, 'quantity': 3, 'unit_price': '100'},
                {'product_id': 7, 'variant_id': None, 'quantity': 1, 'unit_price': '50'},
            ]
        )
        self.assertEqual(len(merged), 2)
        by_key = {(r['product_id'], r['variant_id']): r for r in merged}
        self.assertEqual(by_key[(5, 12)]['quantity'], 5)
        self.assertEqual(by_key[(7, None)]['quantity'], 1)

    def test_empty_input(self):
        self.assertEqual(consolidate_sale_items_data([]), [])
