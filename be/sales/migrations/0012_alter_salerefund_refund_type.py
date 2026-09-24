from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0011_sale_client_channel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='salerefund',
            name='refund_type',
            field=models.CharField(
                choices=[
                    ('full', 'Full refund'),
                    ('partial', 'Partial refund'),
                    ('rollback', 'Rollback'),
                ],
                max_length=20,
            ),
        ),
    ]
