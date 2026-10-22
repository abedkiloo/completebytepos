from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0024_customer_kenya_admin_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='engagement_tier',
            field=models.CharField(
                choices=[
                    ('prospect', 'Registered only'),
                    ('buyer', 'Has bought from Omuwenga'),
                ],
                db_index=True,
                default='prospect',
                help_text='prospect = registered only; buyer = has completed a purchase from Omuwenga.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='buyer_segment',
            field=models.CharField(
                choices=[
                    ('none', 'No purchases'),
                    ('new', 'New buyer'),
                    ('active', 'Active'),
                    ('at_risk', 'At risk'),
                    ('dormant', 'Dormant'),
                    ('champion', 'Champion'),
                ],
                db_index=True,
                default='none',
                help_text='RFM-lite segment for buyers (new/active/at_risk/dormant/champion).',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='purchase_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Completed sales count (excludes fully refunded).',
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='lifetime_sales_value',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Sum of completed sale totals for this customer.',
                max_digits=14,
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='first_purchased_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='last_purchased_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='intelligence_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(
                fields=['engagement_tier', 'buyer_segment'],
                name='sales_cust_tier_seg_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(
                fields=['engagement_tier', 'last_purchased_at'],
                name='sales_cust_tier_last_idx',
            ),
        ),
    ]
