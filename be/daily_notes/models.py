from django.contrib.auth.models import User
from django.db import models


class DailyNote(models.Model):
    """Staff journal entry for a specific calendar day."""

    note_date = models.DateField(db_index=True)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='daily_notes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-note_date', '-created_at']
        indexes = [
            models.Index(fields=['note_date', 'author']),
        ]

    def __str__(self):
        label = self.title or self.content[:40]
        return f'{self.note_date} — {label}'
