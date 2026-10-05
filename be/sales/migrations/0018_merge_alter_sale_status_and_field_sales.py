# Merge UAT leaf 0017_alter_sale_status with 0017_field_sales.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0017_alter_sale_status'),
        ('sales', '0017_field_sales'),
    ]

    operations = []
