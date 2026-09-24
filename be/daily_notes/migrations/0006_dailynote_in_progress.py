from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
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
        migrations.AlterModelOptions(
            name='dailynote',
            options={'ordering': ['-is_sticky', 'is_done', 'in_progress', '-note_date', '-created_at']},
        ),
    ]
