"""
Create exactly three bootstrap users and optionally seed a minimal demo catalog.

Users (default passwords):
  - admin / admin123     → Super Admin (all rights)
  - manager / manager123 → Manager
  - sales / sales123     → Sales Personnel (POS-focused)

Run ``init_permissions`` first (Docker startup does this automatically).
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import UserProfile
from accounts.role_definitions import (
    BOOTSTRAP_USERS,
    ensure_permissions,
    get_role_by_name,
    sync_default_roles,
)


class Command(BaseCommand):
    help = 'Create three bootstrap users (Super Admin, Manager, Sales Personnel)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-seed-products',
            action='store_true',
            help='Skip seeding the 3 demo products',
        )

    def handle(self, *args, **options):
        ensure_permissions()
        roles = sync_default_roles()

        superuser = None
        summary_lines = []

        for spec in BOOTSTRAP_USERS:
            user, created = User.objects.get_or_create(
                username=spec['username'],
                defaults={
                    'email': spec['email'],
                    'is_superuser': spec['is_superuser'],
                    'is_staff': spec['is_staff'],
                    'is_active': True,
                },
            )
            user.email = spec['email']
            user.is_superuser = spec['is_superuser']
            user.is_staff = spec['is_staff']
            user.is_active = True
            user.set_password(spec['password'])
            user.save()

            verb = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'✓ {verb} {spec["label"]}: {spec["username"]}'))

            custom_role = roles.get(spec['custom_role_name']) or get_role_by_name(spec['custom_role_name'])
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': spec['profile_role'],
                    'is_active': True,
                    'custom_role': custom_role,
                },
            )
            profile.role = spec['profile_role']
            profile.is_active = True
            profile.custom_role = custom_role
            if superuser and not profile.created_by_id:
                profile.created_by = superuser
            profile.save()

            if spec['is_superuser']:
                superuser = user

            summary_lines.append(f'   {spec["label"]}: {spec["username"]} / {spec["password"]}')

        if not options['no_seed_products']:
            from django.core.management import call_command
            call_command('seed_demo_catalog', verbosity=1)

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Bootstrap users ready!\n' + '\n'.join(summary_lines)
        ))
