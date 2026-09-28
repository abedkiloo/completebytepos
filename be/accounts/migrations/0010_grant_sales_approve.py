from django.db import migrations


APPROVE_ROLES = (
    'Super Admin',
    'Manager',
    'Admin',
    'Administrator',
)


def grant_sales_approve(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    permission, _ = Permission.objects.update_or_create(
        module='sales',
        action='approve',
        defaults={
            'name': 'sales.approve',
            'description': 'Approve and complete sales submitted by cashiers',
        },
    )
    for role in Role.objects.filter(name__in=APPROVE_ROLES):
        role.permissions.add(permission)


def ungrant_sales_approve(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='sales', action='approve').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_grant_sales_delivery'),
    ]

    operations = [
        migrations.RunPython(grant_sales_approve, ungrant_sales_approve),
    ]
