from django.db import migrations


HISTORY_ROLES = (
    'Super Admin',
    'Manager',
    'Admin',
    'Administrator',
)


def add_delivery_history(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    permission, _ = Permission.objects.update_or_create(
        module='delivery',
        action='history',
        defaults={
            'name': 'delivery.history',
            'description': 'View past delivery routes and completed stops',
        },
    )
    for role in Role.objects.filter(name__in=HISTORY_ROLES):
        role.permissions.add(permission)


def remove_delivery_history(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='delivery', action='history').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_userprofile_must_change_password'),
    ]

    operations = [
        migrations.RunPython(add_delivery_history, remove_delivery_history),
    ]
