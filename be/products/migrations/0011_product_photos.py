import inspect

import django.db.models.deletion
from django.db import migrations, models


def _make_check_constraint(q, name):
    """Build a CheckConstraint for Django 4 or 5."""
    cls = models.CheckConstraint
    params = inspect.signature(cls.__init__).parameters
    if 'condition' in params:
        return cls(condition=q, name=name)
    return cls(check=q, name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_unitofmeasure_alter_product_unit'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='featured_slot',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text='Which saved view is the featured photo. 1–4. Slot 1 when empty.',
            ),
        ),
        migrations.CreateModel(
            name='ProductPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slot', models.PositiveSmallIntegerField(help_text='View number, 1–4. One row per slot.')),
                ('image', models.ImageField(upload_to='products/views/')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='products.product')),
            ],
            options={
                'ordering': ['slot'],
            },
        ),
        migrations.AddConstraint(
            model_name='productphoto',
            constraint=models.UniqueConstraint(fields=('product', 'slot'), name='uniq_product_photo_slot'),
        ),
        migrations.AddConstraint(
            model_name='productphoto',
            constraint=_make_check_constraint(
                models.Q(slot__gte=1, slot__lte=4),
                'product_photo_slot_range',
            ),
        ),
    ]
