import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sales', '0010_rename_sales_sale_occurre_91a2f1_idx_sales_sale_occurre_f971c6_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerSite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(blank=True, max_length=200)),
                ('latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('accuracy', models.FloatField(blank=True, null=True)),
                ('landmark', models.TextField(blank=True)),
                ('is_default', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('finalized', 'Finalized')], default='draft', max_length=20)),
                ('client_uuid', models.UUIDField(blank=True, db_index=True, null=True, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customer_sites_created', to=settings.AUTH_USER_MODEL)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sites', to='sales.customer')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SiteMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='site_media/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('client_uuid', models.UUIDField(blank=True, db_index=True, null=True, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='site_media_created', to=settings.AUTH_USER_MODEL)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='media', to='agents.customersite')),
            ],
            options={
                'verbose_name_plural': 'Site media',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
