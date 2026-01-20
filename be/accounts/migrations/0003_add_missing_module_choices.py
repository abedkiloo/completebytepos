# Generated manually to fix Bug 1: Add missing module choices to Permission model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_permission_module'),
    ]

    operations = [
        migrations.AlterField(
            model_name='permission',
            name='module',
            field=models.CharField(choices=[
                ('products', 'Products'),
                ('categories', 'Categories'),
                ('inventory', 'Inventory'),
                ('sales', 'Sales'),
                ('pos', 'Point of Sale'),
                ('barcodes', 'Barcodes'),
                ('reports', 'Reports'),
                ('expenses', 'Expenses'),
                ('income', 'Income'),
                ('bank_accounts', 'Bank Accounts'),
                ('money_transfer', 'Money Transfer'),
                ('accounting', 'Accounting'),
                ('suppliers', 'Suppliers'),
                ('employees', 'Employee Management'),
                ('customers', 'Customer Management'),
                ('invoicing', 'Invoicing'),
                ('stock', 'Stock Management'),
                ('balance_sheet', 'Balance Sheet'),
                ('trial_balance', 'Trial Balance'),
                ('cash_flow', 'Cash Flow'),
                ('account_statement', 'Account Statement'),
                ('users', 'User Management'),
                ('roles', 'Role Management'),
                ('settings', 'System Settings'),
                ('modules', 'Module Settings'),
            ], max_length=50),
        ),
    ]
