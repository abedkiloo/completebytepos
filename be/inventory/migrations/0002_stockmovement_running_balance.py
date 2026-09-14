from collections import defaultdict

from django.db import migrations, models


def movement_delta(movement):
    mt = movement.movement_type
    qty = int(movement.quantity or 0)
    if mt in ('sale', 'damage', 'waste', 'expired'):
        return -abs(qty)
    if mt in ('purchase', 'return'):
        return abs(qty)
    if mt in ('adjustment', 'transfer'):
        return qty
    return -abs(qty)


def backfill_stock_snapshots(apps, schema_editor):
    StockMovement = apps.get_model('inventory', 'StockMovement')
    Product = apps.get_model('products', 'Product')
    ProductVariant = apps.get_model('products', 'ProductVariant')

    product_qty = dict(Product.objects.values_list('id', 'stock_quantity'))
    variant_qty = dict(ProductVariant.objects.values_list('id', 'stock_quantity'))

    grouped = defaultdict(list)
    for row in StockMovement.objects.order_by('-created_at', '-id').iterator():
        grouped[(row.product_id, row.variant_id)].append(row)

    to_update = []
    for (product_id, variant_id), rows in grouped.items():
        if variant_id:
            running = int(variant_qty.get(variant_id) or 0)
        else:
            running = int(product_qty.get(product_id) or 0)
        for row in rows:
            after = running
            before = after - movement_delta(row)
            row.stock_before = before
            row.stock_after = after
            to_update.append(row)
            running = before

    if to_update:
        StockMovement.objects.bulk_update(
            to_update, ['stock_before', 'stock_after'], batch_size=500
        )


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockmovement',
            name='stock_before',
            field=models.IntegerField(
                blank=True,
                help_text='On-hand quantity immediately before this movement was applied',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='stockmovement',
            name='stock_after',
            field=models.IntegerField(
                blank=True,
                help_text='On-hand quantity immediately after this movement was applied',
                null=True,
            ),
        ),
        migrations.RunPython(backfill_stock_snapshots, migrations.RunPython.noop),
    ]
