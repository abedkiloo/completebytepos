from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0014_merge_duka_fields_and_refund_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sale',
            name='payment_reference',
            field=models.CharField(
                blank=True,
                help_text='M-Pesa confirmation code for non-cash collection',
                max_length=100,
            ),
        ),
    ]
