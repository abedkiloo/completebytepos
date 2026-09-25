from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0015_branch_depot_pin'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='store_name',
            field=models.CharField(
                default='Omuwenga Suppliers',
                help_text=(
                    'Display name shown in the header, login, receipts, and invoices. '
                    'Super admins can edit this in System Settings.'
                ),
                max_length=120,
            ),
        ),
    ]
