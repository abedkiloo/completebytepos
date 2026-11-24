"""Add sales.period_totals — grantable Show total for Sales / Payments trail."""

from django.db import migrations, models


def add_period_totals_permission(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    perm, _ = Permission.objects.get_or_create(
        module='sales',
        action='period_totals',
        defaults={
            'name': 'sales.period_totals',
            'description': (
                'Calculate selected-period money totals '
                '(Sales history and Payments trail Show total)'
            ),
        },
    )
    for role in Role.objects.filter(name='Super Admin'):
        role.permissions.add(perm)


def remove_period_totals_permission(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='sales', action='period_totals').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0020_permission_action_view_cost'),
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
                    ('view_own', 'View own'),
                    ('refund', 'Void / refund'),
                    ('rollback', 'Roll back'),
                    ('unvoid', 'Unvoid / uncancel'),
                    ('correct', 'Correct'),
                    ('profit', 'Trading profit'),
                    ('history', 'History'),
                    ('claim', 'Claim'),
                    ('claim_approve', 'Approve a claim'),
                    ('view_cost', 'See cost of goods'),
                    ('period_totals', 'Period totals'),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(add_period_totals_permission, remove_period_totals_permission),
    ]
