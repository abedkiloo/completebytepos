# Generated manually for SmsTemplate

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('messaging', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmsTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(choices=[('debt_reminder', 'Debt collection reminder')], max_length=64, unique=True)),
                ('body', models.TextField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sms_templates_updated',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['key'],
            },
        ),
    ]
