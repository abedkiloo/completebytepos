# Generated manually for fresh database setup

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('bankaccounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MoneyTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transfer_number', models.CharField(db_index=True, editable=False, max_length=50, unique=True)),
                ('transfer_type', models.CharField(choices=[('bank_to_bank', 'Bank to Bank'), ('bank_to_cash', 'Bank to Cash'), ('cash_to_bank', 'Cash to Bank'), ('cash_to_cash', 'Cash to Cash')], max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0.01)])),
                ('currency', models.CharField(default='KES', max_length=3)),
                ('transfer_date', models.DateField(db_index=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('description', models.TextField()),
                ('reference', models.CharField(blank=True, max_length=100)),
                ('fees', models.DecimalField(decimal_places=2, default=0.0, help_text='Transfer fees', max_digits=10)),
                ('exchange_rate', models.DecimalField(decimal_places=4, default=1.0, help_text='Exchange rate if different currencies', max_digits=10)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transfers_approved', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transfers_created', to=settings.AUTH_USER_MODEL)),
                ('from_account', models.ForeignKey(blank=True, help_text='Source account (null for cash)', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transfers_out', to='bankaccounts.bankaccount')),
                ('to_account', models.ForeignKey(blank=True, help_text='Destination account (null for cash)', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transfers_in', to='bankaccounts.bankaccount')),
            ],
            options={
                'ordering': ['-transfer_date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='moneytransfer',
            index=models.Index(fields=['transfer_date'], name='transfers_mt_date_idx'),
        ),
        migrations.AddIndex(
            model_name='moneytransfer',
            index=models.Index(fields=['status'], name='transfers_mt_status_idx'),
        ),
        migrations.AddIndex(
            model_name='moneytransfer',
            index=models.Index(fields=['from_account', 'to_account'], name='transfers_mt_accounts_idx'),
        ),
    ]
