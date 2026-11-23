from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0019_permission_action_claim'),
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
                ],
                max_length=20,
            ),
        ),
    ]
