import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('settings', '0004_storesettings_receipt_show_sku'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuleSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module', models.CharField(db_index=True, max_length=50)),
                ('key', models.CharField(max_length=100)),
                ('value', models.JSONField(blank=True, null=True)),
                ('label', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('default_value', models.JSONField()),
                ('display_order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'updated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='module_setting_updates',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Module Setting',
                'verbose_name_plural': 'Module Settings',
                'ordering': ['module', 'display_order', 'key'],
                'unique_together': {('module', 'key')},
            },
        ),
        migrations.AddIndex(
            model_name='modulesetting',
            index=models.Index(fields=['module', 'key'], name='settings_mo_module_8a1f2d_idx'),
        ),
    ]
