from django.db import migrations, models


def enable_maker_checker_on_existing_singleton(apps, schema_editor):
    StoreSettings = apps.get_model('settings', 'StoreSettings')
    StoreSettings.objects.filter(pk=1).update(maker_checker_enabled=True)


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0009_alter_storesettings_maker_checker_sales_controls'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storesettings',
            name='maker_checker_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Require checker approval before sensitive price/stock/settings changes go live',
            ),
        ),
        migrations.RunPython(
            enable_maker_checker_on_existing_singleton,
            migrations.RunPython.noop,
        ),
    ]
