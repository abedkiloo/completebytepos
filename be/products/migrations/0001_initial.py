# Generated manually for fresh database setup

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Size',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('code', models.CharField(help_text='Short code (e.g., S, M, L)', max_length=10, unique=True)),
                ('display_order', models.IntegerField(default=0, help_text='Order for display')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Color',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('hex_code', models.CharField(blank=True, help_text='Hex color code (e.g., #FF0000)', max_length=7)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='products.category')),
            ],
            options={
                'verbose_name_plural': 'Categories',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('sku', models.CharField(db_index=True, max_length=50, unique=True)),
                ('barcode', models.CharField(blank=True, db_index=True, max_length=50, null=True, unique=True)),
                ('has_variants', models.BooleanField(default=False, help_text='Does this product have size/color variants?')),
                ('price', models.DecimalField(decimal_places=2, help_text='Selling price', max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('cost', models.DecimalField(decimal_places=2, default=0, help_text='Cost price', max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('stock_quantity', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)])),
                ('low_stock_threshold', models.IntegerField(default=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('reorder_quantity', models.IntegerField(default=50, help_text='Quantity to order when restocking', validators=[django.core.validators.MinValueValidator(0)])),
                ('unit', models.CharField(choices=[('piece', 'Piece'), ('kg', 'Kilogram'), ('g', 'Gram'), ('l', 'Liter'), ('ml', 'Milliliter'), ('box', 'Box'), ('pack', 'Pack'), ('bottle', 'Bottle'), ('can', 'Can')], default='piece', max_length=20)),
                ('image', models.ImageField(blank=True, null=True, upload_to='products/')),
                ('description', models.TextField(blank=True)),
                ('supplier', models.CharField(blank=True, help_text='Supplier name', max_length=200)),
                ('supplier_contact', models.CharField(blank=True, help_text='Supplier contact info', max_length=100)),
                ('tax_rate', models.DecimalField(decimal_places=2, default=0, help_text='Tax rate percentage', max_digits=5, validators=[django.core.validators.MinValueValidator(0)])),
                ('is_taxable', models.BooleanField(default=True)),
                ('track_stock', models.BooleanField(default=True, help_text='Track inventory for this product')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(blank=True, help_text='Main category', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='products.category')),
                ('subcategory', models.ForeignKey(blank=True, help_text='Subcategory (must be a child of the main category)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subcategory_products', to='products.category')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sku', models.CharField(db_index=True, help_text='Variant-specific SKU', max_length=50, unique=True)),
                ('barcode', models.CharField(blank=True, db_index=True, max_length=50, null=True, unique=True)),
                ('price', models.DecimalField(blank=True, decimal_places=2, help_text='Variant-specific price (overrides product price if set)', max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('cost', models.DecimalField(blank=True, decimal_places=2, help_text='Variant-specific cost (overrides product cost if set)', max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('stock_quantity', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)])),
                ('low_stock_threshold', models.IntegerField(blank=True, help_text='Variant-specific low stock threshold', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('color', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='products.color')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variants', to='products.product')),
                ('size', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='products.size')),
            ],
            options={
                'unique_together': {('product', 'size', 'color')},
                'ordering': ['product', 'size', 'color'],
            },
        ),
        migrations.AddField(
            model_name='product',
            name='available_colors',
            field=models.ManyToManyField(blank=True, help_text='Available colors for this product', related_name='products', to='products.color'),
        ),
        migrations.AddField(
            model_name='product',
            name='available_sizes',
            field=models.ManyToManyField(blank=True, help_text='Available sizes for this product', related_name='products', to='products.product'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['sku'], name='products_pr_sku_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['barcode'], name='products_pr_barcode_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['name'], name='products_pr_name_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['is_active'], name='products_pr_is_acti_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['category', 'is_active'], name='products_pr_cat_act_idx'),
        ),
        migrations.AddIndex(
            model_name='productvariant',
            index=models.Index(fields=['sku'], name='products_pv_sku_idx'),
        ),
        migrations.AddIndex(
            model_name='productvariant',
            index=models.Index(fields=['barcode'], name='products_pv_barcode_idx'),
        ),
        migrations.AddIndex(
            model_name='productvariant',
            index=models.Index(fields=['product', 'is_active'], name='products_pv_prod_act_idx'),
        ),
    ]
