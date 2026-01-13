# Generated manually for fresh database setup

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BankAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_name', models.CharField(max_length=200)),
                ('account_number', models.CharField(db_index=True, max_length=100, unique=True)),
                ('bank_name', models.CharField(max_length=200)),
                ('account_type', models.CharField(choices=[('savings', 'Savings'), ('current', 'Current'), ('checking', 'Checking'), ('fixed_deposit', 'Fixed Deposit')], default='current', max_length=20)),
                ('branch', models.CharField(blank=True, max_length=200)),
                ('swift_code', models.CharField(blank=True, max_length=20)),
                ('opening_balance', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, validators=[django.core.validators.MinValueValidator(0.0)])),
                ('current_balance', models.DecimalField(decimal_places=2, default=0.0, help_text='Current balance (calculated from transactions)', max_digits=12)),
                ('currency', models.CharField(default='KES', help_text='Currency code (KES, USD, etc.)', max_length=3)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bank_accounts_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['bank_name', 'account_name'],
            },
        ),
        migrations.CreateModel(
            name='BankTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_number', models.CharField(db_index=True, editable=False, max_length=50, unique=True)),
                ('transaction_type', models.CharField(choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'), ('transfer_in', 'Transfer In'), ('transfer_out', 'Transfer Out'), ('fee', 'Bank Fee'), ('interest', 'Interest')], max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0.01)])),
                ('description', models.TextField()),
                ('reference', models.CharField(blank=True, max_length=100)),
                ('transaction_date', models.DateField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('bank_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='bankaccounts.bankaccount')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bank_transactions_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-transaction_date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='bankaccount',
            index=models.Index(fields=['account_number'], name='bankaccount_account_num_idx'),
        ),
        migrations.AddIndex(
            model_name='bankaccount',
            index=models.Index(fields=['is_active'], name='bankaccount_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='banktransaction',
            index=models.Index(fields=['transaction_date'], name='bankaccount_bt_date_idx'),
        ),
        migrations.AddIndex(
            model_name='banktransaction',
            index=models.Index(fields=['bank_account', 'transaction_date'], name='bankaccount_bt_acc_date_idx'),
        ),
    ]
