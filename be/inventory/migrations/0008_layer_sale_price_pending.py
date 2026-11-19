from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_rename_inventory_s_status_3c8a1a_idx_inventory_s_status_07799e_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='stocklayer',
            name='sale_price_pending',
            field=models.BooleanField(
                default=False,
                help_text='True when this delivery was marked new price and the selling price is not set yet.',
            ),
        ),
        migrations.AddField(
            model_name='stocklayer',
            name='unit_mrp',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                help_text='MRP for this delivery. Empty keeps the product MRP.',
            ),
        ),
    ]
