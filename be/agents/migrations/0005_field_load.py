import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0004_field_sales'),
        ('products', '0010_unitofmeasure_alter_product_unit'),
        ('sales', '0035_call_book'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldLoad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('open', 'Out'), ('pending_review', 'Waiting for manager'), ('accepted', 'Accepted')], db_index=True, default='open', max_length=32)),
                ('review_note', models.CharField(blank=True, default='', max_length=500)),
                ('issued_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_loads', to=settings.AUTH_USER_MODEL)),
                ('issued_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='field_loads_issued', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='field_loads_reviewed', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-issued_at']},
        ),
        migrations.CreateModel(
            name='FieldLoadLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_taken', models.PositiveIntegerField()),
                ('quantity_returned', models.PositiveIntegerField(blank=True, null=True)),
                ('load', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='agents.fieldload')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_load_lines', to='products.product')),
                ('variant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_load_lines', to='products.productvariant')),
            ],
            options={'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='FieldLoadSale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('load', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='load_sales', to='agents.fieldload')),
                ('sale', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='field_load_sale', to='sales.sale')),
            ],
            options={'ordering': ['id']},
        ),
        migrations.AddIndex(
            model_name='fieldload',
            index=models.Index(fields=['agent', 'status'], name='agents_fldload_agent_status'),
        ),
        migrations.AddConstraint(
            model_name='fieldloadline',
            constraint=models.UniqueConstraint(fields=('load', 'product', 'variant'), name='fieldloadline_product_uniq'),
        ),
    ]
