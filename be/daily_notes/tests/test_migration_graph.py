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
        self.assertEqual(
            daily,
            [('daily_notes', '0008_dailynotechecklistitem')],
        )
        self.assertEqual(
            sales,
            [('sales', '0024_customer_kenya_admin_location')],
        )
