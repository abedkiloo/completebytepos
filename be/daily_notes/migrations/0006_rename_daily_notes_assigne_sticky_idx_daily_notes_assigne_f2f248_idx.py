from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('daily_notes', '0005_dailynote_assigned_role'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='dailynote',
            new_name='daily_notes_assigne_f2f248_idx',
            old_name='daily_notes_assigne_sticky_idx',
        ),
    ]
