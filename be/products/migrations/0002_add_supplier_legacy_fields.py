# Generated manually to add legacy supplier fields to existing products table

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_add_supplier_fk_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='supplier_name',
            field=models.CharField(blank=True, help_text='Legacy supplier name (deprecated - use supplier FK)', max_length=200),
        ),
        migrations.AddField(
            model_name='product',
            name='supplier_contact',
            field=models.CharField(blank=True, help_text='Legacy supplier contact (deprecated - use supplier FK)', max_length=100),
        ),
    ]
