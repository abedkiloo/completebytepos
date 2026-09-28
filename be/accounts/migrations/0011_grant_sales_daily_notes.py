from django.db import migrations


SALES_DAILY_NOTES_ACTIONS = ('view', 'create', 'update')

DAILY_NOTES_PERMS = (
    ('view', 'View daily notes'),
    ('create', 'Create daily notes'),
    ('update', 'Update daily notes'),
)


def grant_sales_daily_notes(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    perms = []
    for action, description in DAILY_NOTES_PERMS:
        permission, _ = Permission.objects.update_or_create(
            module='daily_notes',
            action=action,
            defaults={
                'name': f'daily_notes.{action}',
                'description': description,
            },
        )
        perms.append(permission)
    role_ids = (
        Role.objects.filter(
            permissions__module__in=['sales', 'pos'],
            permissions__action='view',
        )
        .values_list('id', flat=True)
        .distinct()
    )
    for role in Role.objects.filter(id__in=role_ids):
        role.permissions.add(*perms)


def ungrant_sales_daily_notes(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    perms = list(
        Permission.objects.filter(
            module='daily_notes',
            action__in=SALES_DAILY_NOTES_ACTIONS,
        )
    )
    if not perms:
        return
    role_ids = (
        Role.objects.filter(
            permissions__module__in=['sales', 'pos'],
            permissions__action='view',
        )
        .values_list('id', flat=True)
        .distinct()
    )
    for role in Role.objects.filter(id__in=role_ids):
        role.permissions.remove(*perms)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_grant_sales_approve'),
    ]

    operations = [
        migrations.RunPython(grant_sales_daily_notes, ungrant_sales_daily_notes),
    ]
