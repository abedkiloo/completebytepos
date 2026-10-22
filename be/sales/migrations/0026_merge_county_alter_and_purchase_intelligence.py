# Merge parallel 0025 leaves:
# - 0025_alter_customer_county_alter_customer_sub_county_and_more
# - 0025_customer_purchase_intelligence

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0025_alter_customer_county_alter_customer_sub_county_and_more'),
        ('sales', '0025_customer_purchase_intelligence'),
    ]

    operations = []
