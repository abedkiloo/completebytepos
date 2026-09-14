from django.conf import settings
from django.db import models

from sales.models import Customer


class CustomerSite(models.Model):
    """
    Field-agent visit location for a customer.

    Delivery stop UI (S09) should treat map + media as first-class:
    lat/lng/accuracy, landmark, label, and ordered SiteMedia thumbnails.
    """

    STATUS_DRAFT = 'draft'
    STATUS_FINALIZED = 'finalized'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_FINALIZED, 'Finalized'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='sites',
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
    )
    accuracy = models.FloatField(null=True, blank=True)
    landmark = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT,
    )
    client_uuid = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_sites_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.label or f'Site {self.pk}'

    @property
    def has_pin(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def media_count(self) -> int:
        return self.media.count()


class SiteMedia(models.Model):
    """Photo attached to a customer site (driver recognition)."""

    site = models.ForeignKey(
        CustomerSite,
        on_delete=models.CASCADE,
        related_name='media',
    )
    image = models.ImageField(upload_to='site_media/')
    caption = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='site_media_created',
    )
    client_uuid = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name_plural = 'Site media'

    def __str__(self):
        return f'Media {self.pk} for site {self.site_id}'


class FieldOrder(models.Model):
    """
    Agent order tied to a CustomerSite.

    Stock policy (DECISIONS): allocate on pack — no reservation in draft/submitted.
    """

    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_PACKING = 'packing'
    STATUS_READY = 'ready'
    STATUS_OUT_FOR_DELIVERY = 'out_for_delivery'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_PACKING, 'Packing'),
        (STATUS_READY, 'Ready'),
        (STATUS_OUT_FOR_DELIVERY, 'Out for delivery'),
        (STATUS_DONE, 'Done'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    site = models.ForeignKey(
        CustomerSite,
        on_delete=models.PROTECT,
        related_name='field_orders',
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='field_orders',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True,
    )
    notes = models.TextField(blank=True)
    client_uuid = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='field_orders_created',
    )
    assigned_delivery_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='field_orders_assigned',
    )
    packed_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    stock_allocated = models.BooleanField(
        default=False,
        help_text='True after allocate-on-pack succeeds',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'FieldOrder {self.pk} ({self.status})'


class FieldOrderLine(models.Model):
    order = models.ForeignKey(
        FieldOrder,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='field_order_lines',
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.PROTECT,
        related_name='field_order_lines',
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    product_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'Line {self.pk} order={self.order_id}'

    @property
    def line_total(self):
        return self.quantity * self.unit_price
