"""
Initialize all permissions and the three bootstrap roles (Super Admin, Manager, Sales Personnel).
"""
from django.core.management.base import BaseCommand

from accounts.role_definitions import ensure_permissions, sync_default_roles


class Command(BaseCommand):
    help = 'Initialize permissions and sync Super Admin / Manager / Sales Personnel roles'

    def handle(self, *args, **options):
        self.stdout.write('Initializing permissions...')
        created = ensure_permissions()
        self.stdout.write(self.style.SUCCESS(f'  ✓ {created} new permissions (all others already exist)'))

        self.stdout.write('Syncing default roles...')
        roles = sync_default_roles()
        for name in roles:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Role "{name}" permissions updated'))

        self.stdout.write(self.style.SUCCESS('\n✅ Permissions and roles initialized successfully!'))
