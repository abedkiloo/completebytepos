import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('agents', '0001_initial'),
        ('products', '0010_unitofmeasure_alter_product_unit'),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('packing', 'Packing'), ('ready', 'Ready'), ('out_for_delivery', 'Out for delivery'), ('done', 'Done'), ('cancelled', 'Cancelled')], db_index=True, default='draft', max_length=32)),
                ('notes', models.TextField(blank=True)),
                ('client_uuid', models.UUIDField(blank=True, db_index=True, null=True, unique=True)),
                ('packed_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_at', models.DateTimeField(blank=True, null=True)),
                ('stock_allocated', models.BooleanField(default=False, help_text='True after allocate-on-pack succeeds')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_delivery_agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='field_orders_assigned', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='field_orders_created', to=settings.AUTH_USER_MODEL)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_orders', to='sales.customer')),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_orders', to='agents.customersite')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='FieldOrderLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=12)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('product_name', models.CharField(blank=True, max_length=255)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='agents.fieldorder')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_order_lines', to='products.product')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
