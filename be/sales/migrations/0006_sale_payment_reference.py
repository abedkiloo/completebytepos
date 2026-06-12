from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0005_rename_sales_sale_refund__b8e2a1_idx_sales_sale_refund__c209d1_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='payment_reference',
            field=models.CharField(
                blank=True,
                help_text='M-Pesa confirmation code, card auth/last-4, or other non-cash reference',
                max_length=100,
            ),
        ),
    ]
