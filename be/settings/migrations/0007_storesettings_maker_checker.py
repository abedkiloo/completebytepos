from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0006_rename_settings_mo_module_8a1f2d_idx_settings_mo_module_66f04d_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='maker_checker_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Require checker approval before sensitive price/stock/settings changes go live',
            ),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='emergency_stock_mode',
            field=models.BooleanField(
                default=False,
                help_text='Allow immediate positive stock adds without maker-checker (still audited)',
            ),
        ),
    ]
