# Generated manually for customer gender (male/female).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0028_rename_sales_cust_tier_seg_idx_sales_custo_engagem_048bb2_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='gender',
            field=models.CharField(
                blank=True,
                choices=[('male', 'Male'), ('female', 'Female')],
                default='',
                help_text='Owner/contact gender. Required for new customers; older records may be blank.',
                max_length=10,
            ),
        ),
    ]
