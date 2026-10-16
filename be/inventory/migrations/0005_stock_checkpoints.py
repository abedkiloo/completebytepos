import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0010_unitofmeasure_alter_product_unit'),
        ('inventory', '0004_rename_inventory_s_product_layer_idx_inventory_s_product_728613_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockCheckpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('open', 'Open'),
                            ('closed', 'Closed'),
                            ('cancelled', 'Cancelled'),
                        ],
                        db_index=True,
                        default='open',
                        max_length=20,
                    ),
                ),
                ('notes', models.TextField(blank=True)),
                ('opened_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('closed_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    'closed_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='stock_checkpoints_closed',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'opened_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='stock_checkpoints_opened',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-opened_at'],
            },
        ),
        migrations.CreateModel(
            name='StockCheckpointLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('system_qty_at_open', models.IntegerField(default=0)),
                ('counted_qty', models.IntegerField(blank=True, null=True)),
                (
                    'unit_cost_snapshot',
                    models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[('pending', 'Pending'), ('counted', 'Counted')],
                        db_index=True,
                        default='pending',
                        max_length=20,
                    ),
                ),
                ('counted_at', models.DateTimeField(blank=True, null=True)),
                (
                    'checkpoint',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='lines',
                        to='inventory.stockcheckpoint',
                    ),
                ),
                (
                    'counted_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='stock_checkpoint_lines_counted',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'movement',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='checkpoint_lines',
                        to='inventory.stockmovement',
                    ),
                ),
                (
                    'product',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='stock_checkpoint_lines',
                        to='products.product',
                    ),
                ),
                (
                    'variant',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='stock_checkpoint_lines',
                        to='products.productvariant',
                    ),
                ),
            ],
            options={
                'ordering': ['product__name', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='stockcheckpoint',
            index=models.Index(fields=['status', 'opened_at'], name='inventory_s_status_3c8a1a_idx'),
        ),
        migrations.AddIndex(
            model_name='stockcheckpoint',
            index=models.Index(fields=['status', 'closed_at'], name='inventory_s_status_9b2e4d_idx'),
        ),
        migrations.AddIndex(
            model_name='stockcheckpointline',
            index=models.Index(fields=['status', 'product'], name='inventory_s_status_7f1c2b_idx'),
        ),
        migrations.AddIndex(
            model_name='stockcheckpointline',
            index=models.Index(fields=['checkpoint', 'status'], name='inventory_s_checkpo_4a8d3e_idx'),
        ),
        migrations.AddConstraint(
            model_name='stockcheckpointline',
            constraint=models.UniqueConstraint(
                fields=('checkpoint', 'product', 'variant'),
                condition=models.Q(variant__isnull=False),
                name='uniq_checkpoint_product_variant',
            ),
        ),
        migrations.AddConstraint(
            model_name='stockcheckpointline',
            constraint=models.UniqueConstraint(
                fields=('checkpoint', 'product'),
                condition=models.Q(variant__isnull=True),
                name='uniq_checkpoint_product_no_variant',
            ),
        ),
    ]
