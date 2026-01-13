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
            name='AccountType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('asset', 'Asset'), ('liability', 'Liability'), ('equity', 'Equity'), ('revenue', 'Revenue'), ('expense', 'Expense')], max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('normal_balance', models.CharField(choices=[('debit', 'Debit'), ('credit', 'Credit')], help_text='Normal balance side for this account type', max_length=10)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_code', models.CharField(db_index=True, max_length=20, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('opening_balance', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('current_balance', models.DecimalField(decimal_places=2, default=0.0, help_text='Current balance (calculated from transactions)', max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='accounts', to='accounting.accounttype')),
                ('parent', models.ForeignKey(blank=True, help_text='Parent account for sub-accounts', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='accounting.account')),
            ],
            options={
                'ordering': ['account_code'],
            },
        ),
        migrations.CreateModel(
            name='JournalEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entry_number', models.CharField(db_index=True, editable=False, max_length=50, unique=True)),
                ('entry_date', models.DateField(db_index=True)),
                ('entry_type', models.CharField(choices=[('debit', 'Debit'), ('credit', 'Credit')], max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0.01)])),
                ('description', models.TextField()),
                ('reference', models.CharField(blank=True, help_text='Reference to source document', max_length=100)),
                ('reference_type', models.CharField(blank=True, help_text='Type of reference (sale, purchase, expense, etc.)', max_length=50)),
                ('reference_id', models.IntegerField(blank=True, help_text='ID of reference document', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='journal_entries', to='accounting.account')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='journal_entries_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Journal Entries',
                'ordering': ['-entry_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_number', models.CharField(db_index=True, editable=False, max_length=50, unique=True)),
                ('transaction_date', models.DateField(db_index=True)),
                ('description', models.TextField()),
                ('reference', models.CharField(blank=True, max_length=100)),
                ('reference_type', models.CharField(blank=True, max_length=50)),
                ('reference_id', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions_created', to=settings.AUTH_USER_MODEL)),
                ('journal_entries', models.ManyToManyField(related_name='transactions', to='accounting.journalentry')),
            ],
            options={
                'ordering': ['-transaction_date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['account_code'], name='accounting_account_code_idx'),
        ),
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['account_type'], name='accounting_account_type_idx'),
        ),
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['is_active'], name='accounting_account_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(fields=['entry_date'], name='accounting_je_entry_date_idx'),
        ),
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(fields=['account', 'entry_date'], name='accounting_je_account_date_idx'),
        ),
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(fields=['reference_type', 'reference_id'], name='accounting_je_ref_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['transaction_date'], name='accounting_txn_date_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['reference_type', 'reference_id'], name='accounting_txn_ref_idx'),
        ),
    ]
