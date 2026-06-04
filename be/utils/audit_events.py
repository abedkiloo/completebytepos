"""Domain-specific audit log writers — thin wrappers over ``audit_helpers``."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Model

from accounts.models import AuditLog
from utils.audit_helpers import log_domain_event, log_model_change


def _money(value) -> str:
    if value is None:
        return ''
    return str(Decimal(str(value)))


def log_sale_completed(request, sale, *, source: str = 'checkout'):
    items = list(sale.items.all()) if hasattr(sale, 'items') else []
    log_domain_event(
        request,
        'checkout' if source == 'checkout' else AuditLog.ACTION_CREATE,
        sale,
        module='sales',
        changes={
            'source': source,
            'sale_number': getattr(sale, 'sale_number', ''),
            'total': _money(getattr(sale, 'total', None)),
            'payment_method': getattr(sale, 'payment_method', ''),
            'status': getattr(sale, 'status', ''),
            'item_count': len(items),
            'customer_id': getattr(sale, 'customer_id', None),
        },
    )


def log_holding_saved(request, holding, *, created: bool):
    log_domain_event(
        request,
        'holding_save',
        holding,
        module='sales',
        changes={
            'created': created,
            'sale_number': getattr(holding, 'sale_number', ''),
            'status': getattr(holding, 'status', ''),
            'item_count': holding.items.count(),
        },
    )


def log_sale_refunded(request, sale, refund):
    log_domain_event(
        request,
        'refund',
        refund,
        module='sales',
        changes={
            'sale_number': getattr(sale, 'sale_number', ''),
            'refund_number': getattr(refund, 'refund_number', ''),
            'refund_type': getattr(refund, 'refund_type', ''),
            'amount': _money(getattr(refund, 'amount', None)),
            'reason': (getattr(refund, 'reason', '') or '')[:500],
            'sale_refund_status': getattr(sale, 'refund_status', ''),
        },
    )


def log_holding_cancelled(request, holding):
    log_domain_event(
        request,
        'holding_cancel',
        holding,
        module='sales',
        changes={'sale_number': getattr(holding, 'sale_number', '')},
    )


def log_product_write(request, product: Model, *, before: Model | None, action: str):
    log_model_change(request, action, product, module='products', before=before)


def log_stock_movement_event(request, movement: Model, *, event: str, payload: dict | None = None):
    changes = dict(payload or {})
    changes['movement_type'] = getattr(movement, 'movement_type', '')
    changes['quantity'] = getattr(movement, 'quantity', None)
    log_domain_event(request, event, movement, module='inventory', changes=changes)


def log_approval_event(request, instance: Model, *, module: str):
    log_domain_event(
        request,
        'approve',
        instance,
        module=module,
        changes={'status': getattr(instance, 'status', '')},
    )


def log_permission_denied(request, *, module: str, action: str, detail: str = ''):
    log_domain_event(
        request,
        AuditLog.ACTION_PERMISSION_DENIED,
        None,
        module=module,
        changes={'action': action, 'detail': detail},
    )
