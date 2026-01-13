# Generated manually for fresh database setup

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '0001_initial'),
        ('settings', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('movement_type', models.CharField(choices=[('sale', 'Sale'), ('purchase', 'Purchase'), ('adjustment', 'Adjustment'), ('return', 'Return'), ('damage', 'Damage'), ('transfer', 'Transfer'), ('waste', 'Waste'), ('expired', 'Expired')], max_length=20)),
                ('quantity', models.IntegerField()),
                ('unit_cost', models.DecimalField(blank=True, decimal_places=2, help_text='Cost per unit for this movement', max_digits=10, null=True)),
                ('total_cost', models.DecimalField(blank=True, decimal_places=2, help_text='Total cost for this movement', max_digits=10, null=True)),
                ('reference', models.CharField(blank=True, max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('branch', models.ForeignKey(blank=True, help_text='Branch where stock movement occurred', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='stock_movements', to='settings.branch')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_movements', to='products.product')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_movements', to=settings.AUTH_USER_MODEL)),
                ('variant', models.ForeignKey(blank=True, help_text='Product variant if applicable', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='stock_movements', to='products.productvariant')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['product', 'created_at'], name='inventory_sm_prod_created_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['movement_type', 'created_at'], name='inventory_sm_type_created_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['created_at'], name='inventory_sm_created_idx'),
        ),
    ]
