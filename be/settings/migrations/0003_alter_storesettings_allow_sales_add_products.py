from django.db import migrations, models


def enable_sales_catalog(apps, schema_editor):
    StoreSettings = apps.get_model('settings', 'StoreSettings')
    StoreSettings.objects.filter(pk=1).update(allow_sales_add_products=True)


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0002_storesettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storesettings',
            name='allow_sales_add_products',
            field=models.BooleanField(
                default=True,
                help_text='Allow sales staff to add products and categories from the catalog UI',
            ),
        ),
        migrations.RunPython(enable_sales_catalog, migrations.RunPython.noop),
    ]
