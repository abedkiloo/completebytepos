from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='IdempotencyRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=255)),
                ('method', models.CharField(max_length=10)),
                ('path', models.CharField(max_length=512)),
                ('request_hash', models.CharField(blank=True, default='', max_length=64)),
                ('status_code', models.PositiveIntegerField()),
                ('response_body', models.TextField(blank=True, default='')),
                ('response_content_type', models.CharField(default='application/json', max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='idempotency_records',
                        to='auth.user',
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name='idempotencyrecord',
            index=models.Index(fields=['key', 'user'], name='idempotency_key_user_idx'),
        ),
        migrations.AddConstraint(
            model_name='idempotencyrecord',
            constraint=models.UniqueConstraint(
                fields=('key', 'user', 'method', 'path'),
                name='uniq_idempotency_key_user_method_path',
            ),
        ),
    ]
