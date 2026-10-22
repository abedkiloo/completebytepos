# Generated to match the leaf that appeared on UAT when help_text was
# added to county / sub_county / ward after 0024 (parallel to
# 0025_customer_purchase_intelligence).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0024_customer_kenya_admin_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='county',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Kenya county (official name).',
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name='customer',
            name='sub_county',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Kenya sub-county within the county.',
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name='customer',
            name='ward',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Kenya ward within the sub-county.',
                max_length=100,
            ),
        ),
    ]
