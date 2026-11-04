from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
        ('cms', '0002_website_manage_permission'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebsiteEnquiry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('phone', models.CharField(max_length=40)),
                ('business', models.CharField(blank=True, max_length=120)),
                ('location', models.CharField(blank=True, max_length=120)),
                ('interest', models.CharField(blank=True, max_length=200)),
                ('message', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('new', 'New'), ('reviewed', 'Reviewed'), ('closed', 'Closed')], db_index=True, default='new', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='website_enquiries', to='products.product')),
            ],
            options={
                'verbose_name_plural': 'website enquiries',
                'ordering': ['-created_at'],
            },
        ),
    ]
