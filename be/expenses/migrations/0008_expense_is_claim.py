from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0007_expense_needs_redo'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='is_claim',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='True when an employee claimed this spend and a manager must decide it.',
            ),
        ),
    ]
