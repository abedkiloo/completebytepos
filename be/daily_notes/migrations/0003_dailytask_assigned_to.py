from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_author_to_assigned_to(apps, schema_editor):
    DailyTask = apps.get_model('daily_notes', 'DailyTask')
    for task in DailyTask.objects.filter(assigned_to_id__isnull=True).iterator():
        task.assigned_to_id = task.author_id
        task.save(update_fields=['assigned_to_id'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('daily_notes', '0002_dailytask'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailytask',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='assigned_daily_tasks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(copy_author_to_assigned_to, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='dailytask',
            name='assigned_to',
            field=models.ForeignKey(
                help_text='Staff member responsible for completing this task.',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='assigned_daily_tasks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name='dailytask',
            index=models.Index(
                fields=['assigned_to', 'is_done'],
                name='daily_notes_assigne_e51852_idx',
            ),
        ),
    ]
