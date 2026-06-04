import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(db_index=True, max_length=64)),
                ('entity_type', models.CharField(db_index=True, max_length=128)),
                ('entity_id', models.CharField(db_index=True, max_length=64)),
                ('entity_repr', models.CharField(blank=True, max_length=255)),
                ('original_values', models.JSONField(default=dict)),
                ('proposed_values', models.JSONField(default=dict)),
                ('reason', models.TextField()),
                ('status', models.CharField(
                    choices=[
                        ('pending_approval', 'Pending approval'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                    ],
                    db_index=True,
                    default='pending_approval',
                    max_length=32,
                )),
                ('batch_id', models.CharField(blank=True, db_index=True, max_length=36)),
                ('made_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('checked_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('apply_payload', models.JSONField(blank=True, default=dict)),
                ('checked_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pending_changes_checked',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('made_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pending_changes_made',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-made_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pendingchange',
            index=models.Index(fields=['status', 'action_type'], name='approvals_p_status_8a0f2d_idx'),
        ),
        migrations.AddIndex(
            model_name='pendingchange',
            index=models.Index(fields=['entity_type', 'entity_id', 'status'], name='approvals_p_entity_66f04d_idx'),
        ),
        migrations.AddIndex(
            model_name='pendingchange',
            index=models.Index(fields=['batch_id', 'status'], name='approvals_p_batch_12ab34_idx'),
        ),
    ]
