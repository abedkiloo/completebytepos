# Add Customer Week promo to SmsTemplate key choices.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0004_alter_smstemplate_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smstemplate',
            name='key',
            field=models.CharField(
                choices=[
                    ('sale_completed', 'Sale completed'),
                    ('debt_settlement', 'Debt payment received'),
                    ('debt_increase', 'Debt increased'),
                    ('debt_reminder', 'Debt collection reminder'),
                    ('invoice_receipt', 'Invoice / payment link'),
                    ('promo_customer_week', 'Customer Week promo'),
                ],
                max_length=64,
                unique=True,
            ),
        ),
    ]
