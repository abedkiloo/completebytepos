# Generated manually for StoreSettings singleton

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('settings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoreSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allow_sales_add_products', models.BooleanField(default=False, help_text='Allow sales staff to add products and categories from the catalog UI')),
                ('sales_catalog_skip_pricing', models.BooleanField(default=True, help_text='When sales add products, skip pricing fields (manager sets prices later)')),
                ('hide_entity_status_toggles', models.BooleanField(default=False, help_text='Hide active/inactive toggles on catalog and user forms')),
                ('enabled_payment_methods', models.JSONField(blank=True, default=list, help_text='Payment methods shown at checkout (cash, mpesa, wallet, card)')),
                ('receipt_logo', models.ImageField(blank=True, null=True, upload_to='receipt/')),
                ('receipt_header_text', models.TextField(blank=True, help_text='Optional message below store name on receipts')),
                ('receipt_footer_text', models.TextField(blank=True, default='Thank you for your business!', help_text='Message at the bottom of printed receipts')),
                ('receipt_show_logo', models.BooleanField(default=True)),
                ('receipt_auto_print', models.BooleanField(default=False, help_text='Automatically open print dialog after completing a sale')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='store_settings_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Store Settings',
                'verbose_name_plural': 'Store Settings',
            },
        ),
    ]
