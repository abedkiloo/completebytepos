from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0012_customer_duka_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='owner_name',
            field=models.CharField(
                blank=True,
                help_text='Owner of the duka.',
                max_length=200,
            ),
        ),
    ]
