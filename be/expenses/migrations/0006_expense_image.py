from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0005_category_include_in_trading_profit'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='image',
            field=models.ImageField(
                blank=True,
                help_text='Optional photo of the expense receipt or proof of payment.',
                null=True,
                upload_to='expenses/',
            ),
        ),
    ]
