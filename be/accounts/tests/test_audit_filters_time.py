from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status

from accounts.models import AuditLog, UserProfile
from accounts.role_definitions import ensure_permissions, sync_default_roles
from utils.tests.api_test_base import SuperAdminAPITestCase


class AuditLogTimeAndFacetsTests(SuperAdminAPITestCase):
    def setUp(self):
        super().setUp()
        ensure_permissions()
        sync_default_roles(created_by=self.admin)
        UserProfile.objects.get_or_create(
            user=self.admin, defaults={'role': 'super_admin', 'is_active': True}
        )
        self.other = User.objects.create_user(username='clerk_a', password='x')
        now = timezone.now()
        AuditLog.objects.create(
            user=self.admin,
            username_snapshot='admin',
            action='create',
            module='products',
            object_repr='Widget',
            created_at=now,
        )
        # Force created_at via queryset update is blocked by immutability on save;
        # create then raw-update the timestamp for filter testing.
        entry = AuditLog.objects.create(
            user=self.other,
            username_snapshot='clerk_a',
            action='stock_adjust',
            module='inventory',
            object_repr='Widget stock',
            changes={'stock_before': 1, 'stock_after': 2},
        )
        AuditLog.objects.filter(pk=entry.pk).update(
            created_at=now.replace(hour=9, minute=15, second=0, microsecond=0)
        )

    def test_facets_lists_modules_and_actions(self):
        res = self.client.get('/api/accounts/audit-logs/facets/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('products', res.data['modules'])
        self.assertIn('inventory', res.data['modules'])
        self.assertIn('create', res.data['actions'])
        self.assertIn('stock_adjust', res.data['actions'])

    def test_filter_by_user_and_module(self):
        res = self.client.get(
            '/api/accounts/audit-logs/',
            {'user': self.other.id, 'module': 'inventory'},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        self.assertTrue(len(rows) >= 1)
        self.assertTrue(all(r['module'] == 'inventory' for r in rows))

    def test_time_from_to_on_day(self):
        day = timezone.localdate().isoformat()
        res = self.client.get(
            '/api/accounts/audit-logs/',
            {
                'date_from': day,
                'date_to': day,
                'time_from': '08:00',
                'time_to': '10:00',
                'module': 'inventory',
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        self.assertTrue(any(r['action'] == 'stock_adjust' for r in rows))
