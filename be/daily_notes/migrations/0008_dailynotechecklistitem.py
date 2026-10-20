from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('daily_notes', '0007_merge_in_progress_and_index_rename'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyNoteChecklistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=200)),
                ('is_done', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'daily_note',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='checklist_items',
                        to='daily_notes.dailynote',
                    ),
                ),
            ],
            options={
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='dailynotechecklistitem',
            index=models.Index(fields=['daily_note', 'is_done'], name='daily_notes_note_check_idx'),
        ),
    ]
