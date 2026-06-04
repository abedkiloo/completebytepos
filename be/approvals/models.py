from django.contrib.auth.models import User
from django.db import models


class PendingChange(models.Model):
    """
    Maker-checker proposal. Live data stays on the entity until status=approved.
    """

    STATUS_PENDING = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    action_type = models.CharField(max_length=64, db_index=True)
    entity_type = models.CharField(max_length=128, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    entity_repr = models.CharField(max_length=255, blank=True)

    original_values = models.JSONField(default=dict)
    proposed_values = models.JSONField(default=dict)
    reason = models.TextField()

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    batch_id = models.CharField(max_length=36, blank=True, db_index=True)

    made_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='pending_changes_made',
    )
    made_at = models.DateTimeField(auto_now_add=True, db_index=True)

    checked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_changes_checked',
    )
    checked_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    apply_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text='Extra data needed to apply on approval (e.g. stock movement params).',
    )

    class Meta:
        ordering = ['-made_at']
        indexes = [
            models.Index(fields=['status', 'action_type']),
            models.Index(fields=['entity_type', 'entity_id', 'status']),
            models.Index(fields=['batch_id', 'status']),
        ]

    def __str__(self):
        return f'{self.action_type} {self.entity_type}:{self.entity_id} ({self.status})'
