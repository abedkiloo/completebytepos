# Expand SmsTemplate key choices for all system SMS templates.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0003_smstemplate'),
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
                ],
                max_length=64,
                unique=True,
            ),
        ),
    ]
