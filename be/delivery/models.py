from django.conf import settings
from django.db import models

from agents.models import FieldOrder


class DeliveryRoute(models.Model):
    """One agent's ordered stops for a calendar day."""

    route_date = models.DateField(db_index=True)
    delivery_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='delivery_routes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-route_date', 'id']
        unique_together = [('route_date', 'delivery_agent')]

    def __str__(self):
        return f'Route {self.route_date} agent={self.delivery_agent_id}'


class DeliveryStop(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ARRIVED = 'arrived'
    STATUS_DELIVERING = 'delivering'
    STATUS_COLLECTED = 'collected'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ARRIVED, 'Arrived'),
        (STATUS_DELIVERING, 'Delivering'),
        (STATUS_COLLECTED, 'Collected'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    route = models.ForeignKey(
        DeliveryRoute,
        on_delete=models.CASCADE,
        related_name='stops',
    )
    field_order = models.OneToOneField(
        FieldOrder,
        on_delete=models.PROTECT,
        related_name='delivery_stop',
    )
    sequence = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True,
    )
    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    collection_method = models.CharField(max_length=32, blank=True)
    collection_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    collection_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sequence', 'id']

    def __str__(self):
        return f'Stop {self.pk} ({self.status})'


class DeliveryLineResult(models.Model):
    stop = models.ForeignKey(
        DeliveryStop,
        on_delete=models.CASCADE,
        related_name='line_results',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='delivery_line_results',
    )
    product_name = models.CharField(max_length=255, blank=True)
    ordered_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    delivered_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    returned_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    stock_applied = models.BooleanField(
        default=False,
        help_text='True after partial/return quantities applied to stock policy',
    )

    class Meta:
        ordering = ['id']
        unique_together = [('stop', 'product')]

    def __str__(self):
        return f'LineResult {self.pk} stop={self.stop_id}'


class ProofOfDelivery(models.Model):
    stop = models.OneToOneField(
        DeliveryStop,
        on_delete=models.CASCADE,
        related_name='pod',
    )
    signature_image = models.ImageField(upload_to='delivery_pod/', blank=True)
    photo = models.ImageField(upload_to='delivery_pod/', blank=True)
    notes = models.TextField(blank=True)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
    )
    captured_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'POD stop={self.stop_id}'

    @property
    def is_complete(self) -> bool:
        has_sig = bool(self.signature_image)
        has_photo = bool(self.photo)
        has_pin = self.latitude is not None and self.longitude is not None
        return has_sig and has_photo and has_pin


class ProposedPinCorrection(models.Model):
    """Optional corrected pin pending manager approval."""

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    stop = models.ForeignKey(
        DeliveryStop,
        on_delete=models.CASCADE,
        related_name='pin_corrections',
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pin_corrections_proposed',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'PinCorrection {self.pk} ({self.status})'
