from django.db import migrations


SALES_DELIVERY_ROLES = (
    'Sales Personnel',
    'Field Sales',
)


def grant_sales_delivery(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    perms = []
    for action, description in (
        ('view', 'View delivery routes and stops'),
        ('update', 'Arrive, deliver, collect, POD, complete stops'),
    ):
        permission, _ = Permission.objects.update_or_create(
            module='delivery',
            action=action,
            defaults={
                'name': f'delivery.{action}',
                'description': description,
            },
        )
        perms.append(permission)
    for role in Role.objects.filter(name__in=SALES_DELIVERY_ROLES):
        role.permissions.add(*perms)


def ungrant_sales_delivery(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    perms = list(
        Permission.objects.filter(
            module='delivery',
            action__in=['view', 'update'],
        )
    )
    if not perms:
        return
    for role in Role.objects.filter(name__in=SALES_DELIVERY_ROLES):
        role.permissions.remove(*perms)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_grant_debt_collection_approve'),
    ]

    operations = [
        migrations.RunPython(grant_sales_delivery, ungrant_sales_delivery),
    ]
