# Heal denormalized tiers after 0025 fields land (defaults alone leave buyers as prospect).

from django.db import migrations


def forwards(apps, schema_editor):
    from sales.customer_intelligence import backfill_customer_intelligence

    backfill_customer_intelligence(batch_size=500)


def backwards(apps, schema_editor):
    Customer = apps.get_model('sales', 'Customer')
    Customer.objects.all().update(
        engagement_tier='prospect',
        buyer_segment='none',
        purchase_count=0,
        lifetime_sales_value=0,
        first_purchased_at=None,
        last_purchased_at=None,
        intelligence_updated_at=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0026_merge_county_alter_and_purchase_intelligence'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
