"""
Field-agent visit sites, media, and packable field orders.

Public entry points:
    - ``CustomerSite`` / ``SiteMedia`` — visit location and driver-recognition photos
    - ``FieldOrder`` / ``FieldOrderLine`` — order lifecycle; pack creates one sale
    - ``order_services.pack_order`` / ``field_sale.record_field_sale`` — sale path

Side effects: none at model layer. Packing (services) moves stock, posts journals,
and records customer debt via ``sales.Sale``. Stock is not reserved in draft/submitted.

Invariants: at most one ``Sale`` per ``FieldOrder`` (``OneToOne`` on ``sale``).
"""

from django.conf import settings
from django.db import models

from sales.models import Customer


class CustomerSite(models.Model):
    """
    Field-agent visit location tied to an optional customer.

    Holds map pin (lat/lng/accuracy), landmark text, label, and ordered
    ``SiteMedia`` for driver recognition. Finalized sites require pin + customer
    (photos optional when ``MIN_SITE_MEDIA`` is 0).

    Attributes:
        STATUS_DRAFT: Editable visit; orders may reference but submit checks apply.
        STATUS_FINALIZED: Pin and customer locked by ``finalize_site``.
        client_uuid: Optional mobile idempotency key; unique when set.
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
        """Return whether both latitude and longitude are set."""
        return self.latitude is not None and self.longitude is not None

    @property
    def media_count(self) -> int:
        """Return the number of ``SiteMedia`` rows for this site (0 if none)."""
        return self.media.count()


class SiteMedia(models.Model):
    """
    Photo attached to a customer site for driver recognition.

    Images upload to ``site_media/``. Clients may supply ``client_uuid`` for
    offline idempotency; duplicate UUIDs are rejected at the DB layer.

    Attributes:
        caption: Optional short label (max 255 chars).
    """

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
    Agent order tied to a ``CustomerSite``; packs into a single POS sale.

    Status flows draft → submitted → packing → ready → out_for_delivery → done
    (or cancelled). Stock and accounting apply on pack only — no reservation
    while draft or submitted.

    Attributes:
        stock_allocated: Set True when pack succeeds (allocate-on-pack).
        sale: One-to-one link to the ``sales.Sale`` created at pack; null until packed.
        assigned_delivery_agent: Driver/sales user with ``delivery.update`` after assign.
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
    sale = models.OneToOneField(
        'sales.Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='field_order',
        help_text='Sale recorded for the agent when the order was packed',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'FieldOrder {self.pk} ({self.status})'


class FieldOrderLine(models.Model):
    """
    One product line on a field order before pack.

    ``quantity`` uses three decimal places in storage; sale recording requires
    a whole-number quantity at pack time. ``unit_price`` is money (2 dp).

    Attributes:
        product_name: Snapshot label; falls back to product name when blank.
        line_total: Computed ``quantity * unit_price`` (not persisted).
    """

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
