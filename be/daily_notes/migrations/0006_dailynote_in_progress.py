from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('daily_notes', '0005_dailynote_assigned_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailynote',
            name='in_progress',
            field=models.BooleanField(
                default=False,
                help_text='True while the note is in the Doing column of the board.',
            ),
        ),
        migrations.AlterField(
            model_name='dailynote',
            name='is_sticky',
            field=models.BooleanField(
                default=False,
                help_text='When true, the assignee must tick this note before using the rest of the system.',
            ),
        ),
        migrations.AlterField(
            model_name='dailynote',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True,
                help_text='Staff member who must resolve this note.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_daily_notes',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name='dailynote',
            options={'ordering': ['-is_sticky', 'is_done', 'in_progress', '-note_date', '-created_at']},
        ),
    ]

