# Generated manually — MRP (list price) separate from selling price (transactions).

from decimal import Decimal
from django.db import migrations, models
import django.core.validators


def copy_price_to_mrp(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductVariant = apps.get_model('products', 'ProductVariant')
    for product in Product.objects.all().iterator():
        if product.mrp is None or product.mrp == Decimal('0'):
            Product.objects.filter(pk=product.pk).update(mrp=product.price)
    for variant in ProductVariant.objects.all().iterator():
        if variant.mrp is None or variant.mrp == Decimal('0'):
            parent = Product.objects.filter(pk=variant.product_id).first()
            fallback = variant.price if variant.price is not None else (parent.price if parent else Decimal('0'))
            ProductVariant.objects.filter(pk=variant.pk).update(mrp=fallback)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='mrp',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Maximum retail price (MRP) — list/sticker price for display',
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='mrp',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Variant MRP (overrides product MRP when set)',
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(
                decimal_places=2,
                help_text='Selling price — used for POS, sales, invoices, and reports',
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AlterField(
            model_name='productvariant',
            name='price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Variant selling price (overrides product selling price when set)',
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.RunPython(copy_price_to_mrp, migrations.RunPython.noop),
    ]
