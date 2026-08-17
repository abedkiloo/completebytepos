from django.db import migrations, models


def relax_default_backfill_window(apps, schema_editor):
    StoreSettings = apps.get_model('settings', 'StoreSettings')
    # The previous default of 30 blocked shops catching up older paper sales.
    StoreSettings.objects.filter(backfill_max_days=30).update(backfill_max_days=0)


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0013_storesettings_backfill'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storesettings',
            name='backfill_max_days',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    'Maximum days in the past staff may record an offline sale. '
                    '0 means no limit (any past date).'
                ),
            ),
        ),
        migrations.RunPython(relax_default_backfill_window, migrations.RunPython.noop),
    ]
