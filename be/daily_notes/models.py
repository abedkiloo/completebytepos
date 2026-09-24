from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class DailyNote(models.Model):
    """Staff journal entry for a specific calendar day."""

    note_date = models.DateField(db_index=True)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    is_sticky = models.BooleanField(
        default=False,
        help_text='When true, the assignee must tick this note before using the rest of the system.',
    )
    in_progress = models.BooleanField(
        default=False,
        help_text='True while the note is in the Doing column of the board.',
    )
    is_done = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='daily_notes',
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_daily_notes',
        help_text='Staff member who must resolve this note.',
    )
    assigned_role = models.ForeignKey(
        'accounts.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_notes',
        help_text='When set, a copy is created for every active user with this role.',
    )
    assignment_group = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Shared id for notes fanned out to a role.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_sticky', 'is_done', 'in_progress', '-note_date', '-created_at']
        indexes = [
            models.Index(fields=['note_date', 'author']),
            models.Index(fields=['assigned_to', 'is_sticky', 'is_done']),
        ]

    def __str__(self):
        label = self.title or self.content[:40]
        kind = 'must-tick' if self.is_sticky else 'note'
        return f'{self.note_date} — {label} ({kind})'

    def mark_done(self, *, done: bool, at=None):
        self.is_done = done
        self.completed_at = (at or timezone.now()) if done else None
        if done:
            self.in_progress = False

    def move_to_board(self, column: str):
        column = (column or '').strip().lower()
        if column == 'past':
            self.mark_done(done=True)
        elif column == 'doing':
            self.mark_done(done=False)
            self.in_progress = True
        else:
            self.mark_done(done=False)
            self.in_progress = False

    @property
    def board_column(self) -> str:
        if self.is_done:
            return 'past'
        if self.in_progress:
            return 'doing'
        return 'todo'


class DailyTask(models.Model):
    """Checklist item for a specific calendar day."""

    task_date = models.DateField(db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_done = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='daily_tasks',
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_daily_tasks',
        help_text='Staff member responsible for completing this task.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['is_done', '-task_date', '-created_at']
        indexes = [
            models.Index(fields=['task_date', 'author']),
            models.Index(fields=['task_date', 'is_done']),
            models.Index(fields=['assigned_to', 'is_done']),
        ]

    def __str__(self):
        status = 'done' if self.is_done else 'open'
        return f'{self.task_date} — {self.title} ({status})'

    def mark_done(self, *, done: bool, at=None):
        self.is_done = done
        self.completed_at = (at or timezone.now()) if done else None
