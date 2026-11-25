"""Clarify view_all action label and sales.view_all description."""

from django.db import migrations, models


def update_sales_view_all_description(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='sales', action='view_all').update(
        description=(
            'View other staff sales (not only your own — history, daily, dashboard)'
        ),
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0021_permission_action_period_totals'),
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
                    ('view_all', "View others' records"),
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
        migrations.RunPython(update_sales_view_all_description, noop_reverse),
    ]
