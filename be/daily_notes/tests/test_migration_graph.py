"""Guard against forked migration graphs (UAT makemigrations leaves)."""

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase


class MigrationGraphTests(TestCase):
    def test_daily_notes_and_sales_have_one_leaf(self):
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        leaves = loader.graph.leaf_nodes()
        daily = [node for node in leaves if node[0] == 'daily_notes']
        sales = [node for node in leaves if node[0] == 'sales']
        self.assertEqual(len(daily), 1, daily)
        self.assertEqual(daily[0][0], 'daily_notes')
        self.assertEqual(len(sales), 1, sales)
        self.assertEqual(sales[0][0], 'sales')
        # Leaves move as migrations land — assert a single tip, not a fixed name.
        self.assertTrue(daily[0][1])
        self.assertTrue(sales[0][1])
