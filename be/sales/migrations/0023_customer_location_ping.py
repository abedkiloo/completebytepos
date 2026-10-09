from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0022_merge_stock_layers_and_index_rename'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='Map pin latitude snapped when registering this duka.',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='Map pin longitude snapped when registering this duka.',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='location_accuracy',
            field=models.FloatField(
                blank=True,
                help_text='GPS accuracy in metres when the location was snapped.',
                null=True,
            ),
        ),
    ]
