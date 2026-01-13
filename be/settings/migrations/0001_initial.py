# Generated manually for fresh database setup

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuleSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module_name', models.CharField(choices=[('products', 'Products Management'), ('sales', 'Sales'), ('customers', 'Customer Management'), ('invoicing', 'Invoicing'), ('inventory', 'Inventory Management'), ('stock', 'Stock Management'), ('expenses', 'Expenses'), ('income', 'Income'), ('bank_accounts', 'Bank Accounts'), ('money_transfer', 'Money Transfer'), ('accounting', 'Accounting'), ('balance_sheet', 'Balance Sheet'), ('trial_balance', 'Trial Balance'), ('cash_flow', 'Cash Flow'), ('account_statement', 'Account Statement'), ('barcodes', 'Barcodes'), ('reports', 'Reports'), ('settings', 'System Settings')], max_length=50, unique=True)),
                ('is_enabled', models.BooleanField(default=True, help_text='Enable or disable this module')),
                ('description', models.TextField(blank=True, help_text='Module description')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modules_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Module Setting',
                'verbose_name_plural': 'Module Settings',
                'ordering': ['module_name'],
                'db_table': 'accounts_modulesettings',
            },
        ),
        migrations.CreateModel(
            name='ModuleFeature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feature_key', models.CharField(help_text='Feature identifier (e.g., qr_printing)', max_length=100)),
                ('feature_name', models.CharField(help_text='Feature display name', max_length=200)),
                ('is_enabled', models.BooleanField(default=True, help_text='Enable or disable this feature')),
                ('description', models.TextField(blank=True, help_text='Feature description')),
                ('display_order', models.IntegerField(default=0, help_text='Order for display in UI')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('module', models.ForeignKey(help_text='Parent module', on_delete=django.db.models.deletion.CASCADE, related_name='features', to='settings.modulesettings')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='features_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Module Feature',
                'verbose_name_plural': 'Module Features',
                'ordering': ['module', 'display_order', 'feature_name'],
                'unique_together': {('module', 'feature_key')},
                'db_table': 'accounts_modulefeature',
            },
        ),
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, help_text='Business/Company name', max_length=200)),
                ('code', models.CharField(db_index=True, help_text='Unique tenant code', max_length=50, unique=True)),
                ('registration_number', models.CharField(blank=True, help_text='Business registration number', max_length=100)),
                ('tax_id', models.CharField(blank=True, help_text='Tax ID or VAT number', max_length=50)),
                ('address', models.TextField(blank=True, help_text='Business address')),
                ('city', models.CharField(blank=True, max_length=100)),
                ('country', models.CharField(default='Kenya', max_length=100)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('website', models.URLField(blank=True)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this tenant is active')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tenants_created', to=settings.AUTH_USER_MODEL)),
                ('owner', models.ForeignKey(blank=True, help_text='Primary owner/administrator of this business', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_tenants', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Tenant',
                'verbose_name_plural': 'Tenants',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='tenant',
            index=models.Index(fields=['code'], name='settings_te_code_idx'),
        ),
        migrations.AddIndex(
            model_name='tenant',
            index=models.Index(fields=['name'], name='settings_te_name_idx'),
        ),
        migrations.AddIndex(
            model_name='tenant',
            index=models.Index(fields=['is_active'], name='settings_te_is_acti_idx'),
        ),
        migrations.CreateModel(
            name='Branch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('branch_code', models.CharField(db_index=True, help_text='Unique branch code within tenant', max_length=50)),
                ('name', models.CharField(db_index=True, help_text='Branch name', max_length=200)),
                ('address', models.TextField(blank=True, help_text='Branch address')),
                ('city', models.CharField(blank=True, max_length=100)),
                ('country', models.CharField(default='Kenya', max_length=100)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this branch is active')),
                ('is_headquarters', models.BooleanField(default=False, help_text='Mark as headquarters/main branch for this tenant')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='branches_created', to=settings.AUTH_USER_MODEL)),
                ('manager', models.ForeignKey(blank=True, help_text='Branch manager', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_branches', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Business/Company this branch belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='branches', to='settings.tenant')),
            ],
            options={
                'verbose_name': 'Branch',
                'verbose_name_plural': 'Branches',
                'ordering': ['tenant', 'name'],
                'unique_together': {('tenant', 'branch_code')},
            },
        ),
        migrations.AddIndex(
            model_name='branch',
            index=models.Index(fields=['tenant', 'branch_code'], name='settings_br_tenant_branch_idx'),
        ),
        migrations.AddIndex(
            model_name='branch',
            index=models.Index(fields=['tenant', 'name'], name='settings_br_tenant_name_idx'),
        ),
        migrations.AddIndex(
            model_name='branch',
            index=models.Index(fields=['is_active'], name='settings_br_is_acti_idx'),
        ),
        migrations.AddIndex(
            model_name='branch',
            index=models.Index(fields=['is_headquarters'], name='settings_br_is_head_idx'),
        ),
    ]
