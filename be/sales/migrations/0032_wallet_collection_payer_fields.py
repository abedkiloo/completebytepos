from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0031_sale_status_discarded'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerwallettransaction',
            name='payer_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Name of the person who paid (may differ from the customer on file).',
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name='customerwallettransaction',
            name='payer_phone',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Phone number of the person who paid.',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='customerwallettransaction',
            name='mpesa_destination',
            field=models.CharField(
                blank=True,
                choices=[('till', 'Till'), ('bank', 'Bank')],
                default='',
                help_text='For M-Pesa codes: till or bank. Blank for cash / non-code flows.',
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name='customerwallettransaction',
            index=models.Index(
                fields=['mpesa_destination', 'reference'],
                name='sales_custo_mpesa_d_idx',
            ),
        ),
    ]
