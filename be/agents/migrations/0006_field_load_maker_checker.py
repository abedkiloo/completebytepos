import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0005_field_load'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='fieldload',
            name='issue_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='fieldload',
            name='issue_approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='field_loads_issue_approved',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='fieldload',
            name='status',
            field=models.CharField(
                choices=[
                    ('awaiting_issue', 'Waiting for quantity confirmation'),
                    ('open', 'Out'),
                    ('pending_review', 'Waiting for manager'),
                    ('accepted', 'Accepted'),
                    ('issue_rejected', 'Sent back'),
                ],
                db_index=True,
                default='open',
                max_length=32,
            ),
        ),
    ]
