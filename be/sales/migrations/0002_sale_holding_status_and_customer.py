# Generated manually for holding-invoice POS flow

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='status',
            field=models.CharField(
                choices=[
                    ('holding', 'Holding'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='completed',
                help_text='Holding = draft invoice at the register; completed = stock moved and sale finalised.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                help_text='Customer attached to this sale (optional for walk-in).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sales',
                to='sales.customer',
            ),
        ),
        migrations.AlterField(
            model_name='sale',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('cash', 'Cash'),
                    ('mpesa', 'M-PESA'),
                    ('card', 'Card'),
                    ('other', 'Other'),
                ],
                default='cash',
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name='sale',
            index=models.Index(fields=['status', 'cashier'], name='sales_sale_status__a1b2c3_idx'),
        ),
    ]
