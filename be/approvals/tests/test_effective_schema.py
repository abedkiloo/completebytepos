"""Pending-change overlay when DB schema is present."""

from django.test import TestCase

from approvals.effective import pending_schema_ready


class PendingSchemaReadyTests(TestCase):
    def test_pending_schema_ready_after_migrate(self):
        self.assertTrue(pending_schema_ready())
