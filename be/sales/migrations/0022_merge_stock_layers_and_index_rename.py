# Merge parallel 0021 leaves: stock layers FIFO + index rename autodetection.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0021_stock_layers_fifo'),
        (
            'sales',
            '0021_rename_sales_custo_source__7c2a1b_idx_sales_custo_source__2a6bfc_idx_and_more',
        ),
    ]

    operations = []
