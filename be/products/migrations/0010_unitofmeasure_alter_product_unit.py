# Generated manually for extensible units of measure

from django.db import migrations, models


def seed_units(apps, schema_editor):
    UnitOfMeasure = apps.get_model('products', 'UnitOfMeasure')
    rows = [
        ('piece', 'Piece', 1),
        ('kg', 'Kilogram', 2),
        ('g', 'Gram', 3),
        ('l', 'Liter', 4),
        ('ml', 'Milliliter', 5),
        ('box', 'Box', 6),
        ('pack', 'Pack', 7),
        ('bottle', 'Bottle', 8),
        ('can', 'Can', 9),
        ('roll', 'Roll', 10),
    ]
    for code, label, order in rows:
        UnitOfMeasure.objects.update_or_create(
            code=code,
            defaults={'label': label, 'display_order': order, 'is_active': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_product_mrp'),
    ]

    operations = [
        migrations.CreateModel(
            name='UnitOfMeasure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=20, unique=True)),
                ('label', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Unit of measure',
                'verbose_name_plural': 'Units of measure',
                'ordering': ['display_order', 'label'],
            },
        ),
        migrations.AlterField(
            model_name='product',
            name='unit',
            field=models.CharField(
                default='piece',
                help_text='Unit code — must match an active UnitOfMeasure.code',
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_units, migrations.RunPython.noop),
    ]
