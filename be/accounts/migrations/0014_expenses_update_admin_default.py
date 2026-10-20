"""Make expenses.update admin-only by default (still grantable on roles)."""

from django.db import migrations


ADMIN_ROLE_NAMES = (
    'Super Admin',
    'Admin',
    'Administrator',
)


def revoke_expenses_update_from_non_admins(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    perm = Permission.objects.filter(module='expenses', action='update').first()
    if not perm:
        return
    Permission.objects.filter(pk=perm.pk).update(
        description=(
            'Edit expenses (admin by default; grant to roles that may correct expenses)'
        ),
    )
    for role in Role.objects.exclude(name__in=ADMIN_ROLE_NAMES):
        role.permissions.remove(perm)


def restore_expenses_update_to_manager(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    perm = Permission.objects.filter(module='expenses', action='update').first()
    if not perm:
        return
    manager = Role.objects.filter(name='Manager').first()
    if manager:
        manager.permissions.add(perm)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_debt_management_payments_trail'),
    ]

    operations = [
        migrations.RunPython(
            revoke_expenses_update_from_non_admins,
            restore_expenses_update_to_manager,
        ),
    ]
