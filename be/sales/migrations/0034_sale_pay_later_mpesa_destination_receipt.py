from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0033_wallet_receipt_image_occurred_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sale',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('cash', 'Cash'),
                    ('mpesa', 'M-PESA'),
                    ('on_account', 'Pay later'),
                    ('card', 'Card'),
                    ('other', 'Other'),
                ],
                default='cash',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='mpesa_destination',
            field=models.CharField(
                blank=True,
                choices=[('', '—'), ('till', 'Till'), ('bank', 'Bank')],
                default='',
                help_text='Till or bank when collecting M-Pesa at the sale.',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='payment_receipt_image',
            field=models.ImageField(
                blank=True,
                help_text='Screenshot of the M-Pesa / bank payment confirmation at checkout.',
                null=True,
                upload_to='sale_payment_receipts/',
            ),
        ),
    ]
