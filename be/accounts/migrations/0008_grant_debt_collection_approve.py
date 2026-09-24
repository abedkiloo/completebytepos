from django.db import migrations


APPROVE_ROLES = (
    'Super Admin',
    'Manager',
    'Admin',
    'Administrator',
)


def grant_debt_collection_approve(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    permission, _ = Permission.objects.update_or_create(
        module='debt_management',
        action='approve',
        defaults={
            'name': 'debt_management.approve',
            'description': 'Approve customer debt collections',
        },
    )
    Permission.objects.filter(module='debt_management', action='update').update(
        description=(
            'Collect customer debt payments (queued for manager approval unless you can approve)'
        ),
        name='debt_management.update',
    )
    for role in Role.objects.filter(name__in=APPROVE_ROLES):
        role.permissions.add(permission)


def ungrant_debt_collection_approve(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='debt_management', action='approve').delete()
    Permission.objects.filter(module='debt_management', action='update').update(
        description='Collect and record customer debt payments',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_delivery_history_permission'),
    ]

    operations = [
        migrations.RunPython(grant_debt_collection_approve, ungrant_debt_collection_approve),
    ]
