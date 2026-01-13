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
            name='Permission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module', models.CharField(choices=[('products', 'Products'), ('categories', 'Categories'), ('inventory', 'Inventory'), ('sales', 'Sales'), ('pos', 'Point of Sale'), ('barcodes', 'Barcodes'), ('reports', 'Reports'), ('expenses', 'Expenses'), ('income', 'Income'), ('bank_accounts', 'Bank Accounts'), ('money_transfer', 'Money Transfer'), ('accounting', 'Accounting'), ('users', 'User Management'), ('roles', 'Role Management'), ('settings', 'System Settings'), ('modules', 'Module Settings')], max_length=50)),
                ('action', models.CharField(choices=[('view', 'View'), ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('approve', 'Approve'), ('export', 'Export'), ('import', 'Import'), ('manage', 'Manage')], max_length=20)),
                ('name', models.CharField(help_text='Unique permission name (e.g., products.view)', max_length=100, unique=True)),
                ('description', models.TextField(blank=True, help_text='Permission description')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Permission',
                'verbose_name_plural': 'Permissions',
                'ordering': ['module', 'action'],
                'unique_together': {('module', 'action')},
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_system_role', models.BooleanField(default=False, help_text='System roles cannot be deleted')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='roles_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Role',
                'verbose_name_plural': 'Roles',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('super_admin', 'Super Admin'), ('admin', 'Admin'), ('manager', 'Manager'), ('cashier', 'Cashier')], default='cashier', help_text='Legacy role field', max_length=20)),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('is_active', models.BooleanField(default=True, help_text='User account status')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users_created', to=settings.AUTH_USER_MODEL)),
                ('custom_role', models.ForeignKey(blank=True, help_text='Custom role with specific permissions', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users', to='accounts.role')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Profile',
                'verbose_name_plural': 'User Profiles',
            },
        ),
        migrations.AddField(
            model_name='role',
            name='permissions',
            field=models.ManyToManyField(blank=True, related_name='roles', to='accounts.permission'),
        ),
    ]
