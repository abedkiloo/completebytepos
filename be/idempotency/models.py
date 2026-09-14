from django.conf import settings
from django.db import models


class IdempotencyRecord(models.Model):
    """Stores the first successful (or completed) response for an Idempotency-Key."""

    key = models.CharField(max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='idempotency_records',
    )
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=512)
    request_hash = models.CharField(max_length=64, blank=True, default='')
    status_code = models.PositiveIntegerField()
    response_body = models.TextField(blank=True, default='')
    response_content_type = models.CharField(max_length=128, default='application/json')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['key', 'user', 'method', 'path'],
                name='uniq_idempotency_key_user_method_path',
            ),
        ]
        indexes = [
            models.Index(fields=['key', 'user']),
        ]

    def __str__(self):
        return f'{self.method} {self.path} [{self.key}]'
