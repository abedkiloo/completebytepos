from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0012_alter_storesettings_maker_checker_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='backfill_max_days',
            field=models.PositiveIntegerField(
                default=30,
                help_text='Maximum days in the past staff may record an offline sale.',
            ),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='backfill_maker_checker_enabled',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'When maker-checker is on, past sale entries require checker approval before '
                    'stock and accounts are updated. Turn off to apply backfills immediately.'
                ),
            ),
        ),
    ]
