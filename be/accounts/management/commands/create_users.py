"""
Create exactly three bootstrap users (no product/category seeding).

Users (default passwords — applied only when the user is first created):
  - admin / admin123     → Super Admin (all rights)
  - manager / manager123 → Manager
  - sales / sales123     → Sales Personnel (POS-focused)

Redeploys call this on every container start. Existing passwords are left alone
unless ``--reset-passwords`` is passed. Optional env overrides for first create:
  BOOTSTRAP_ADMIN_PASSWORD, BOOTSTRAP_MANAGER_PASSWORD, BOOTSTRAP_SALES_PASSWORD

Run ``init_permissions`` first (Docker startup does this automatically).
"""
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import UserProfile
from accounts.role_definitions import (
    BOOTSTRAP_USERS,
    ensure_permissions,
    get_role_by_name,
    sync_default_roles,
)

_ENV_PASSWORD_KEYS = {
    'admin': 'BOOTSTRAP_ADMIN_PASSWORD',
    'manager': 'BOOTSTRAP_MANAGER_PASSWORD',
    'sales': 'BOOTSTRAP_SALES_PASSWORD',
}


def _password_for(spec: dict) -> str:
    env_key = _ENV_PASSWORD_KEYS.get(spec['username'])
    if env_key:
        from_env = (os.environ.get(env_key) or '').strip()
        if from_env:
            return from_env
    return spec['password']


class Command(BaseCommand):
    help = (
        'Create three bootstrap users (Super Admin, Manager, Sales Personnel). '
        'Does not reset passwords on existing users unless --reset-passwords.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help=(
                'Force bootstrap/default passwords onto existing users. '
                'Destructive — only use for local recovery.'
            ),
        )

    def handle(self, *args, **options):
        reset_passwords = bool(options.get('reset_passwords'))
        ensure_permissions()
        roles = sync_default_roles()

        superuser = None
        summary_lines = []

        for spec in BOOTSTRAP_USERS:
            password = _password_for(spec)
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
            password_touched = False
            if created or reset_passwords:
                user.set_password(password)
                password_touched = True
            user.save()

            verb = 'Created' if created else 'Updated'
            pwd_note = (
                ' (password set)'
                if password_touched
                else ' (password unchanged)'
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ {verb} {spec["label"]}: {spec["username"]}{pwd_note}')
            )

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

            if password_touched:
                summary_lines.append(
                    f'   {spec["label"]}: {spec["username"]} / {password}'
                )
            else:
                summary_lines.append(
                    f'   {spec["label"]}: {spec["username"]} (existing password kept)'
                )

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Bootstrap users ready!\n' + '\n'.join(summary_lines)
        ))
