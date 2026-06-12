"""Keep parent product stock aligned with variant rows."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from products.models import ProductVariant
from products.stock_utils import sync_product_stock_from_variants


@receiver(post_save, sender=ProductVariant)
def sync_parent_stock_after_variant_save(sender, instance, **kwargs):
    product = instance.product
    if product.has_variants and product.track_stock:
        sync_product_stock_from_variants(product)


@receiver(post_delete, sender=ProductVariant)
def sync_parent_stock_after_variant_delete(sender, instance, **kwargs):
    product = instance.product
    if product.has_variants and product.track_stock:
        sync_product_stock_from_variants(product)
