import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_stock_layers_fifo'),
        ('sales', '0020_debtsettlementallocation_and_wallet_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='saleitem',
            name='unit_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Layer COGS for this line (FIFO stock layer at sale time).',
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.CreateModel(
            name='SaleItemLayerAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('qty_returned', models.PositiveIntegerField(
                    default=0,
                    help_text='Units already restored to the layer via refunds.',
                )),
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
                ('sale_item', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='layer_allocations',
                    to='sales.saleitem',
                )),
                ('stock_layer', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sale_allocations',
                    to='inventory.stocklayer',
                )),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
