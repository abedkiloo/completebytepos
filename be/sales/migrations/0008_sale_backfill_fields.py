from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def copy_created_at_to_occurred_at(apps, schema_editor):
    Sale = apps.get_model('sales', 'Sale')
    for sale in Sale.objects.filter(occurred_at__isnull=True).iterator():
        sale.occurred_at = sale.created_at or timezone.now()
        sale.save(update_fields=['occurred_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0007_alter_customerwallettransaction_source_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='occurred_at',
            field=models.DateTimeField(
                db_index=True,
                help_text='When the sale actually happened (business date for reports).',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='entry_source',
            field=models.CharField(
                choices=[
                    ('pos', 'POS'),
                    ('billing', 'Billing'),
                    ('normal', 'Normal sale'),
                    ('backfill', 'Past sale entry'),
                ],
                db_index=True,
                default='pos',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='backfill_reason',
            field=models.TextField(
                blank=True,
                help_text='Required when entry_source is backfill — why this sale is being entered late.',
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='served_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Staff member who made the sale (commission attribution). Defaults to cashier.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sales_served',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(copy_created_at_to_occurred_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='sale',
            name='occurred_at',
            field=models.DateTimeField(
                db_index=True,
                help_text='When the sale actually happened (business date for reports).',
            ),
        ),
        migrations.AddIndex(
            model_name='sale',
            index=models.Index(fields=['occurred_at'], name='sales_sale_occurre_91a2f1_idx'),
        ),
        migrations.AddIndex(
            model_name='sale',
            index=models.Index(fields=['served_by', 'occurred_at'], name='sales_sale_served__4c8e21_idx'),
        ),
        migrations.AddIndex(
            model_name='sale',
            index=models.Index(fields=['entry_source', 'occurred_at'], name='sales_sale_entry_s_7b3a44_idx'),
        ),
    ]
