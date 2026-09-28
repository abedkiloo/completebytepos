from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0014_merge_duka_fields_and_refund_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sale',
            name='status',
            field=models.CharField(
                choices=[
                    ('holding', 'Holding'),
                    ('pending_approval', 'Pending approval'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='completed',
                help_text=(
                    'Holding = draft at the register; pending_approval = waiting for a manager; '
                    'completed = stock moved and sale finalised.'
                ),
                max_length=20,
            ),
        ),
    ]
