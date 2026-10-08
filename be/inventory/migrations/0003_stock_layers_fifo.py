import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def create_opening_layers(apps, schema_editor):
    """Migrate current on-hand stock into one opening layer per SKU."""
    Product = apps.get_model('products', 'Product')
    ProductVariant = apps.get_model('products', 'ProductVariant')
    StockLayer = apps.get_model('inventory', 'StockLayer')
    now = django.utils.timezone.now()

    for product in Product.objects.filter(track_stock=True).iterator():
        if product.has_variants:
            for variant in ProductVariant.objects.filter(product_id=product.id):
                qty = int(variant.stock_quantity or 0)
                if qty <= 0:
                    continue
                cost = variant.cost if variant.cost is not None else product.cost
                price = variant.price if variant.price is not None else product.price
                StockLayer.objects.create(
                    product_id=product.id,
                    variant_id=variant.id,
                    qty_received=qty,
                    qty_remaining=qty,
                    unit_cost=cost or 0,
                    unit_sell_price=price or 0,
                    received_at=now,
                    source_movement=None,
                )
        else:
            qty = int(product.stock_quantity or 0)
            if qty <= 0:
                continue
            StockLayer.objects.create(
                product_id=product.id,
                variant_id=None,
                qty_received=qty,
                qty_remaining=qty,
                unit_cost=product.cost or 0,
                unit_sell_price=product.price or 0,
                received_at=now,
                source_movement=None,
            )


def noop_reverse(apps, schema_editor):
    StockLayer = apps.get_model('inventory', 'StockLayer')
    StockLayer.objects.filter(source_movement__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_stockmovement_running_balance'),
        ('products', '0010_unitofmeasure_alter_product_unit'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockLayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qty_received', models.PositiveIntegerField()),
                ('qty_remaining', models.PositiveIntegerField()),
                ('unit_cost', models.DecimalField(
                    decimal_places=2,
                    max_digits=10,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('unit_sell_price', models.DecimalField(
                    decimal_places=2,
                    max_digits=10,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('received_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_layers',
                    to='products.product',
                )),
                ('source_movement', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_layers',
                    to='inventory.stockmovement',
                )),
                ('variant', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_layers',
                    to='products.productvariant',
                )),
            ],
            options={
                'ordering': ['received_at', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='stocklayer',
            index=models.Index(
                fields=['product', 'variant', 'received_at'],
                name='inventory_s_product_layer_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='stocklayer',
            index=models.Index(
                fields=['product', 'qty_remaining'],
                name='inventory_s_product_qtyrem_idx',
            ),
        ),
        migrations.RunPython(create_opening_layers, noop_reverse),
    ]
