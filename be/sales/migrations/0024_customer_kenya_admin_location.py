from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0023_customer_location_ping'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='county',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='customer',
            name='sub_county',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='customer',
            name='ward',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
