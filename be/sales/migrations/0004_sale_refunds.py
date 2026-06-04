import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sales', '0003_rename_sales_sale_status__a1b2c3_idx_sales_sale_status_fb684c_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='refund_status',
            field=models.CharField(
                choices=[
                    ('none', 'None'),
                    ('partial', 'Partially refunded'),
                    ('refunded', 'Fully refunded'),
                ],
                db_index=True,
                default='none',
                help_text='Whether this completed sale has been partially or fully refunded.',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='SaleRefund',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('refund_number', models.CharField(db_index=True, editable=False, max_length=50, unique=True)),
                ('refund_type', models.CharField(choices=[('full', 'Full refund'), ('partial', 'Partial refund')], max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('reason', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('refunded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sale_refunds_processed', to=settings.AUTH_USER_MODEL)),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='refunds', to='sales.sale')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SaleRefundItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('subtotal', models.DecimalField(decimal_places=2, max_digits=10)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='products.product')),
                ('refund', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='sales.salerefund')),
                ('sale_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='refund_lines', to='sales.saleitem')),
                ('variant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='products.productvariant')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='sale',
            index=models.Index(fields=['refund_status', 'created_at'], name='sales_sale_refund__b8e2a1_idx'),
        ),
    ]
