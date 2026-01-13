# Generated manually for fresh database setup

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('settings', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='IncomeCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'Income Categories',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Income',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('income_number', models.CharField(db_index=True, editable=False, max_length=50, unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0.01)])),
                ('description', models.TextField()),
                ('payment_method', models.CharField(choices=[('cash', 'Cash'), ('mpesa', 'M-PESA'), ('bank', 'Bank Transfer'), ('card', 'Card'), ('other', 'Other')], default='cash', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('received', 'Received')], default='pending', max_length=20)),
                ('payer', models.CharField(blank=True, help_text='Payer name', max_length=200)),
                ('reference_number', models.CharField(blank=True, max_length=100)),
                ('income_date', models.DateField()),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incomes_approved', to=settings.AUTH_USER_MODEL)),
                ('branch', models.ForeignKey(blank=True, help_text='Branch where income was received', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='incomes', to='settings.branch')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incomes', to='income.incomecategory')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incomes_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-income_date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='income',
            index=models.Index(fields=['income_date'], name='income_inco_inc_date_idx'),
        ),
        migrations.AddIndex(
            model_name='income',
            index=models.Index(fields=['status'], name='income_inco_status_idx'),
        ),
        migrations.AddIndex(
            model_name='income',
            index=models.Index(fields=['category', 'income_date'], name='income_inco_cat_date_idx'),
        ),
    ]
