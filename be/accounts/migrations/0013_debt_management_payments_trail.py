from django.db import migrations, models


# Sales desk roles keep debt collect/view but must not open the store-wide trail.
SALES_ROLE_NAMES = (
    'Sales Personnel',
    'Field Sales',
    'Field Agent',  # legacy name
    'Cashier',
)


def add_payments_trail_permission(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')

    permission, _ = Permission.objects.update_or_create(
        module='debt_management',
        action='payments_trail',
        defaults={
            'name': 'debt_management.payments_trail',
            'description': 'View store-wide payments trail (managers — not sales staff)',
        },
    )

    # Grant to roles that already manage debt, except sales desk personas.
    role_ids = (
        Role.objects.filter(
            permissions__module='debt_management',
            permissions__action='view',
        )
        .exclude(name__in=SALES_ROLE_NAMES)
        .values_list('id', flat=True)
        .distinct()
    )
    for role in Role.objects.filter(id__in=role_ids):
        role.permissions.add(permission)


def remove_payments_trail_permission(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='debt_management', action='payments_trail').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_alter_permission_module'),
    ]

    operations = [
        migrations.AlterField(
            model_name='permission',
            name='action',
            field=models.CharField(
                choices=[
                    ('view', 'View'),
                    ('create', 'Create'),
                    ('update', 'Update'),
                    ('delete', 'Delete'),
                    ('approve', 'Approve'),
                    ('export', 'Export'),
                    ('import', 'Import'),
                    ('manage', 'Manage'),
                    ('payments_trail', 'Payments trail'),
                    ('daily_sales', 'Daily sales'),
                    ('view_all', 'View all'),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(add_payments_trail_permission, remove_payments_trail_permission),
    ]
