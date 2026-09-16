from django.db import migrations, models


DEBT_PERMISSIONS = (
    ('view', 'View debt management and aging reports'),
    ('update', 'Collect and record customer debt payments'),
    ('export', 'Export debt management reports'),
)


def add_debt_permissions(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')

    created = {}
    for action, description in DEBT_PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            module='debt_management',
            action=action,
            defaults={
                'name': f'debt_management.{action}',
                'description': description,
            },
        )
        created[action] = permission

    # Preserve existing access while making it independently revocable.
    customer_to_debt = {
        'view': 'view',
        'update': 'update',
        'export': 'export',
    }
    for customer_action, debt_action in customer_to_debt.items():
        role_ids = Role.objects.filter(
            permissions__module='customers',
            permissions__action=customer_action,
        ).values_list('id', flat=True)
        for role in Role.objects.filter(id__in=role_ids):
            role.permissions.add(created[debt_action])


def remove_debt_permissions(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='debt_management').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_permission_module'),
    ]

    operations = [
        migrations.AlterField(
            model_name='permission',
            name='module',
            field=models.CharField(
                choices=[
                    ('products', 'Products'),
                    ('categories', 'Categories'),
                    ('inventory', 'Inventory'),
                    ('sales', 'Sales'),
                    ('pos', 'Point of Sale'),
                    ('barcodes', 'Barcodes'),
                    ('reports', 'Reports'),
                    ('expenses', 'Expenses'),
                    ('income', 'Income'),
                    ('bank_accounts', 'Bank Accounts'),
                    ('money_transfer', 'Money Transfer'),
                    ('accounting', 'Accounting'),
                    ('suppliers', 'Suppliers'),
                    ('employees', 'Employee Management'),
                    ('customers', 'Customer Management'),
                    ('debt_management', 'Debt Management'),
                    ('invoicing', 'Invoicing'),
                    ('agents', 'Customer sites'),
                    ('dispatch', 'Dispatch'),
                    ('delivery', 'Delivery'),
                    ('payments', 'Payments'),
                    ('messaging', 'Messaging'),
                    ('daily_notes', 'Daily Notes'),
                    ('stock', 'Stock Management'),
                    ('balance_sheet', 'Balance Sheet'),
                    ('trial_balance', 'Trial Balance'),
                    ('cash_flow', 'Cash Flow'),
                    ('account_statement', 'Account Statement'),
                    ('users', 'User Management'),
                    ('roles', 'Role Management'),
                    ('settings', 'System Settings'),
                    ('modules', 'Module Settings'),
                ],
                max_length=50,
            ),
        ),
        migrations.RunPython(add_debt_permissions, remove_debt_permissions),
    ]
