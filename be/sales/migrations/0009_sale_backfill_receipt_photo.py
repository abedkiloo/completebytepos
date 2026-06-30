from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0008_sale_backfill_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='backfill_receipt_photo',
            field=models.ImageField(
                blank=True,
                help_text='Optional photo of the paper receipt for past sale entries.',
                null=True,
                upload_to='sale_backfill/',
            ),
        ),
    ]
