from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0018_merge_alter_sale_status_and_field_sales'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerwallettransaction',
            name='payment_method',
            field=models.CharField(
                blank=True,
                default='',
                help_text='How a debt settlement was paid (cash / mpesa). Blank for non-settlement rows.',
                max_length=20,
            ),
        ),
    ]
