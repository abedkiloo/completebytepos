from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0011_sale_client_channel'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='contact_person',
            field=models.CharField(
                blank=True,
                help_text='Person to ask for at the duka, if different from the owner.',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='typical_goods',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Goods this duka usually buys.',
            ),
        ),
    ]
