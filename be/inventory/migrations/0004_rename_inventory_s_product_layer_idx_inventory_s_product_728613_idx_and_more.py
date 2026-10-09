# Align StockLayer index names with Django autodetection.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_stock_layers_fifo'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='stocklayer',
            new_name='inventory_s_product_728613_idx',
            old_name='inventory_s_product_layer_idx',
        ),
        migrations.RenameIndex(
            model_name='stocklayer',
            new_name='inventory_s_product_bf3b66_idx',
            old_name='inventory_s_product_qtyrem_idx',
        ),
    ]
