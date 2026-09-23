from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0014_relax_backfill_max_days'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='Depot pin for delivery maps (shop start).',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='branch',
            name='longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='Depot pin for delivery maps (shop start).',
                max_digits=10,
                null=True,
            ),
        ),
    ]
