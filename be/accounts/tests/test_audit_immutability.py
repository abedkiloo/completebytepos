from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import AuditLog


class AuditLogImmutabilityTests(TestCase):
    def test_existing_rows_cannot_be_updated(self):
        user = User.objects.create_user(username='audit_imm', password='x')
        entry = AuditLog.objects.create(
            user=user,
            username_snapshot='audit_imm',
            action='create',
            module='products',
            object_type='products.Product',
            object_id='1',
            object_repr='Widget',
            changes={'stock_before': 1, 'stock_after': 2},
        )
        entry.action = 'update'
        with self.assertRaises(ValueError):
            entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.action, 'create')
