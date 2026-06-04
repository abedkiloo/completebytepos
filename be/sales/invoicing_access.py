"""Invoicing catalog feature gates."""

from __future__ import annotations

from settings.module_features import is_module_feature_enabled


def invoice_creation_allowed() -> bool:
    return is_module_feature_enabled('invoicing', 'invoice_creation')


def invoice_tracking_allowed() -> bool:
    return is_module_feature_enabled('invoicing', 'invoice_tracking')


def payment_tracking_allowed() -> bool:
    return is_module_feature_enabled('invoicing', 'payment_tracking')
