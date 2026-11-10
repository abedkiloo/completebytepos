from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0032_wallet_collection_payer_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerwallettransaction',
            name='receipt_image',
            field=models.ImageField(
                blank=True,
                help_text='Screenshot or photo of the M-Pesa (or other) repayment receipt.',
                null=True,
                upload_to='debt_receipts/',
            ),
        ),
        migrations.AddField(
            model_name='customerwallettransaction',
            name='occurred_at',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text=(
                    'Business time the customer paid. May differ from created_at when '
                    'staff record a past-day repayment. Null on legacy rows — use created_at.'
                ),
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name='customerwallettransaction',
            index=models.Index(
                fields=['source_type', 'occurred_at'],
                name='sales_custo_source__occur_idx',
            ),
        ),
    ]
