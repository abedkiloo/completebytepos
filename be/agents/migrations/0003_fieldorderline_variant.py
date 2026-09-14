# Generated manually for FieldOrderLine.variant

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_unitofmeasure_alter_product_unit'),
        ('agents', '0002_fieldorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='fieldorderline',
            name='variant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='field_order_lines',
                to='products.productvariant',
            ),
        ),
    ]
