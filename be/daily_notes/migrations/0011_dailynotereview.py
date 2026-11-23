from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('daily_notes', '0010_dailynote_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyNoteReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Waiting for review'), ('reviewed', 'Reviewed')], db_index=True, default='pending', max_length=16)),
                ('comment', models.CharField(blank=True, max_length=500)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('daily_note', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='daily_notes.dailynote')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_note_review_requests', to=settings.AUTH_USER_MODEL)),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_note_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='dailynotereview',
            constraint=models.UniqueConstraint(fields=('daily_note', 'reviewer'), name='daily_notes_one_reviewer_per_note'),
        ),
    ]
