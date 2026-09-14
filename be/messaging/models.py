from django.conf import settings
from django.db import models


class MessageOutbox(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    TEMPLATE_INVOICE = 'invoice_receipt'
    TEMPLATE_DEBT_REMINDER = 'debt_reminder'

    to_phone = models.CharField(max_length=20)
    body = models.TextField()
    template_key = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True,
    )
    provider = models.CharField(max_length=32, blank=True)
    provider_ref = models.CharField(max_length=128, blank=True)
    error = models.TextField(blank=True)
    payment_intent = models.ForeignKey(
        'payments.PaymentIntent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
    )
    customer = models.ForeignKey(
        'sales.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Message outbox'

    def __str__(self):
        return f'Message {self.pk} → {self.to_phone} ({self.status})'
