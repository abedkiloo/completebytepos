from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryroute',
            name='encoded_polyline',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Cached Google encoded polyline for this day’s stops. Rebuild when stops change.',
            ),
        ),
        migrations.AddField(
            model_name='deliveryroute',
            name='polyline_source',
            field=models.CharField(
                blank=True,
                default='',
                help_text='google | straight | empty',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='deliveryroute',
            name='geometry_fingerprint',
            field=models.CharField(blank=True, default='', max_length=2048),
        ),
        migrations.AddField(
            model_name='deliveryroute',
            name='geometry_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
