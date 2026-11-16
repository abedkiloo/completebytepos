from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0036_call_follow_up'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sale',
            name='entry_source',
            field=models.CharField(
                choices=[
                    ('pos', 'POS'),
                    ('billing', 'Billing'),
                    ('normal', 'Normal sale'),
                    ('backfill', 'Past sale entry'),
                    ('field', 'Field sale'),
                    ('field_load', 'Field load sale'),
                ],
                db_index=True,
                default='pos',
                max_length=20,
            ),
        ),
    ]
