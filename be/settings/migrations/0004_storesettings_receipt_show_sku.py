from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0003_alter_storesettings_allow_sales_add_products'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='receipt_show_sku',
            field=models.BooleanField(
                default=False,
                help_text='Show product SKU on printed and preview receipts',
            ),
        ),
    ]
