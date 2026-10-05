# Generated on UAT; kept in-repo so it merges cleanly with 0017_field_sales.
# Adds awaiting_payment to Sale.status choices (also included in 0017_field_sales).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0016_merge_payment_reference_and_pending_approval'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sale',
            name='status',
            field=models.CharField(
                choices=[
                    ('holding', 'Holding'),
                    ('pending_approval', 'Pending approval'),
                    ('awaiting_payment', 'Awaiting payment'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='completed',
                help_text=(
                    'Holding = draft at the register; pending_approval = waiting for a manager; '
                    'awaiting_payment = approved, collect funds; completed = stock moved and sale finalised.'
                ),
                max_length=20,
            ),
        ),
    ]
