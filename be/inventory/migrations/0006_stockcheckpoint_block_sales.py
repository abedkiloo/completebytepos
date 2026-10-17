from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_stock_checkpoints'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockcheckpoint',
            name='block_sales',
            field=models.BooleanField(
                default=True,
                help_text='When True, pending lines cannot be sold until counted.',
            ),
        ),
    ]
