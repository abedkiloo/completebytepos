from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0030_enable_customer_edit_for_app'),
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
                    ('discarded', 'Permanently removed'),
                ],
                db_index=True,
                default='completed',
                help_text=(
                    'Holding = draft at the register; pending_approval = waiting for a '
                    'manager; awaiting_payment = approved, collect funds; completed = '
                    'stock moved and sale finalised; discarded = permanently removed '
                    'after return for correction (hidden from lists and reports).'
                ),
                max_length=20,
            ),
        ),
    ]
