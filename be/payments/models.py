import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class PaymentIntent(models.Model):
    STATUS_CREATED = 'created'
    STATUS_PROMPTED = 'prompted'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_PROMPTED, 'Prompted'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    PURPOSE_POS = 'pos'
    PURPOSE_DEBT = 'debt'
    PURPOSE_DELIVERY = 'delivery'
    PURPOSE_OTHER = 'other'
    PURPOSE_CHOICES = [
        (PURPOSE_POS, 'POS'),
        (PURPOSE_DEBT, 'Debt settle'),
        (PURPOSE_DELIVERY, 'Delivery collect'),
        (PURPOSE_OTHER, 'Other'),
    ]

    client_uuid = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED, db_index=True,
    )
    purpose = models.CharField(
        max_length=20, choices=PURPOSE_CHOICES, default=PURPOSE_OTHER,
    )
    customer = models.ForeignKey(
        'sales.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_intents',
    )
    customer_name = models.CharField(max_length=200, blank=True)
    invoice_number = models.CharField(max_length=50, blank=True)
    public_token = models.CharField(max_length=64, unique=True, db_index=True)
    checkout_request_id = models.CharField(max_length=64, blank=True, db_index=True)
    merchant_request_id = models.CharField(max_length=64, blank=True)
    mpesa_receipt = models.CharField(max_length=64, blank=True)
    failure_reason = models.TextField(blank=True)
    callback_payload = models.JSONField(null=True, blank=True)
    callback_processed = models.BooleanField(default=False)
    sms_queued = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_intents_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    prompted_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'PaymentIntent {self.pk} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(24)
        if not self.invoice_number:
            self.invoice_number = f'INV-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            self.STATUS_PAID,
            self.STATUS_FAILED,
            self.STATUS_CANCELLED,
            self.STATUS_EXPIRED,
        }
