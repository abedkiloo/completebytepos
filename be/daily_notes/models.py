"""
Staff daily notes, checklists, and standalone tasks.

Public entry points:
    - ``DailyNote`` / ``DailyNoteChecklistItem`` / ``DailyTask`` models
    - Board helpers ``mark_done`` / ``move_to_board`` on notes

Mutations do not write ``AuditLog`` from the model layer alone.
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

PRIORITY_HIGH = 'high'
PRIORITY_MEDIUM = 'medium'
PRIORITY_LOW = 'low'
PRIORITY_CHOICES = [
    (PRIORITY_HIGH, 'Highest'),
    (PRIORITY_MEDIUM, 'Medium'),
    (PRIORITY_LOW, 'Less'),
]
# Sort key: highest first (0), then medium (1), then less (2).
PRIORITY_ORDER = {
    PRIORITY_HIGH: 0,
    PRIORITY_MEDIUM: 1,
    PRIORITY_LOW: 2,
}


def priority_sort_case(field_name: str = 'priority'):
    """
    Django ``Case`` expression sorting highest → medium → less.

    Args:
        field_name: Model field holding priority choice (max 32 chars).

    Returns:
        ``Case`` annotated as IntegerField (0–2).
    """
    from django.db.models import Case, IntegerField, Value, When

    return Case(
        When(**{field_name: PRIORITY_HIGH}, then=Value(0)),
        When(**{field_name: PRIORITY_MEDIUM}, then=Value(1)),
        When(**{field_name: PRIORITY_LOW}, then=Value(2)),
        default=Value(1),
        output_field=IntegerField(),
    )


class DailyNote(models.Model):
    """
    Staff journal entry for a calendar day with optional assignment.

    Sticky notes block POS until the assignee marks them done. ``title`` max
    200 chars; ``content`` is required text. ``priority`` is high/medium/low.
    """

    note_date = models.DateField(db_index=True)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    priority = models.CharField(
        max_length=16,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        db_index=True,
        help_text='Highest, medium, or less — drives board colour and sort order.',
    )
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
    image = models.ImageField(
        upload_to='daily_notes/',
        blank=True,
        null=True,
        help_text='Optional photo attached to this note (receipt, damage, handover proof).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_sticky', 'is_done', 'in_progress', '-note_date', '-created_at']
        indexes = [
            models.Index(
                fields=['note_date', 'author'],
                name='daily_notes_note_da_78a6b0_idx',
            ),
            models.Index(
                fields=['assigned_to', 'is_sticky', 'is_done'],
                name='daily_notes_assigne_f2f248_idx',
            ),
            models.Index(
                fields=['priority', 'is_done'],
                name='daily_notes_priority_done_idx',
            ),
        ]

    def __str__(self):
        label = self.title or self.content[:40]
        kind = 'must-tick' if self.is_sticky else 'note'
        return f'{self.note_date} — {label} ({kind}, {self.priority})'

    def mark_done(self, *, done: bool, at=None):
        """
        Set completion state and timestamp.

        Args:
            done: When ``True``, sets ``completed_at`` to ``at`` or ``timezone.now()``
                and clears ``in_progress``. When ``False``, clears ``completed_at``.
            at: Optional timezone-aware completion time when ``done=True``.

        Returns:
            None. Updates fields in memory; caller must ``save()``.
        """
        self.is_done = done
        self.completed_at = (at or timezone.now()) if done else None
        if done:
            self.in_progress = False

    def move_to_board(self, column: str):
        """
        Map a kanban column name to note status fields.

        Args:
            column: ``'past'`` marks done; ``'doing'`` sets in progress; any other
                value (including ``'todo'``) clears in progress and open state.

        Returns:
            None. Updates fields in memory; caller must ``save()``.
        """
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
        """
        Derive kanban column from current flags.

        Returns:
            ``'past'``, ``'doing'``, or ``'todo'``.
        """
        if self.is_done:
            return 'past'
        if self.in_progress:
            return 'doing'
        return 'todo'


class DailyNoteChecklistItem(models.Model):
    """Optional checkable row attached to a daily note (note text stays required)."""

    daily_note = models.ForeignKey(
        DailyNote,
        on_delete=models.CASCADE,
        related_name='checklist_items',
    )
    label = models.CharField(max_length=200)
    is_done = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']
        indexes = [
            models.Index(
                fields=['daily_note', 'is_done'],
                name='daily_notes_note_check_idx',
            ),
        ]

    def __str__(self):
        status = 'done' if self.is_done else 'open'
        return f'{self.label} ({status})'

    def mark_done(self, *, done: bool, at=None):
        """
        Set checklist row completion.

        Args:
            done: Completion flag; sets ``completed_at`` when ``True``.
            at: Optional completion timestamp; defaults to ``timezone.now()``.

        Returns:
            None. Caller must ``save()``.
        """
        self.is_done = done
        self.completed_at = (at or timezone.now()) if done else None


class DailyTask(models.Model):
    """Standalone checklist item for a specific calendar day."""

    task_date = models.DateField(db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=16,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        db_index=True,
        help_text='Highest, medium, or less — colour and sort for the day list.',
    )
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
            models.Index(
                fields=['task_date', 'author'],
                name='daily_notes_task_da_99b33a_idx',
            ),
            models.Index(
                fields=['task_date', 'is_done'],
                name='daily_notes_task_da_5f2376_idx',
            ),
            models.Index(
                fields=['assigned_to', 'is_done'],
                name='daily_notes_assigne_e51852_idx',
            ),
            models.Index(
                fields=['priority', 'is_done'],
                name='daily_notes_task_priority_idx',
            ),
        ]

    def __str__(self):
        status = 'done' if self.is_done else 'open'
        return f'{self.task_date} — {self.title} ({status}, {self.priority})'

    def mark_done(self, *, done: bool, at=None):
        """
        Set task completion state.

        Args:
            done: When ``True``, records ``completed_at`` (``at`` or now).
            at: Optional timezone-aware completion instant.

        Returns:
            None. Caller must ``save()``.
        """
        self.is_done = done
        self.completed_at = (at or timezone.now()) if done else None
