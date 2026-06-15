"""
Maker-checker workflow: submit, approve, reject, validate.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from approvals.models import PendingChange
from approvals.permissions import (
    is_emergency_stock_mode,
    is_maker_checker_enabled,
    user_can_check,
    user_may_approve_change,
)
from approvals.registry import (
    ACTION_PRODUCT_PRICE,
    ACTION_PRODUCT_STOCK,
    ACTION_STOCK_ADJUST,
    ACTION_STOCK_PURCHASE,
    ACTION_STOCK_TRANSFER,
    CHECKER_MODULE_BY_ACTION,
    classify_product_field_changes,
    classify_variant_field_changes,
)


class MakerCheckerRequired(Exception):
    """Raised when a write was routed to pending instead of live data."""

    def __init__(self, change: PendingChange):
        self.change = change
        super().__init__('Change submitted for approval, not yet active.')


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'pk'):
        return value.pk
    if hasattr(value, 'name'):
        try:
            return str(value.name) if value else ''
        except ValueError:
            return ''
    return value


def snapshot_model(instance, fields: Optional[List[str]] = None) -> Dict[str, Any]:
    from django.forms.models import model_to_dict

    data = model_to_dict(instance, fields=fields)
    return {k: _json_safe(v) for k, v in data.items()}


def _audit_pending(request, change: PendingChange, action: str, extra: dict | None = None):
    from utils.audit_helpers import log_domain_event

    changes = {
        'pending_change_id': change.id,
        'action_type': change.action_type,
        'status': change.status,
        'original_values': change.original_values,
        'proposed_values': change.proposed_values,
        'reason': change.reason,
    }
    if extra:
        changes.update(extra)
    log_domain_event(
        request,
        action,
        module='approvals',
        changes=changes,
        object_repr=str(change),
    )


@transaction.atomic
def submit_change(
    *,
    request,
    action_type: str,
    entity_type: str,
    entity_id,
    entity_repr: str,
    original_values: dict,
    proposed_values: dict,
    reason: str,
    apply_payload: dict | None = None,
    batch_id: str = '',
) -> PendingChange:
    if not reason or not str(reason).strip():
        raise ValidationError({'reason': 'A reason is required for maker-checker proposals.'})
    if not is_maker_checker_enabled():
        raise ValidationError('Maker-checker is not enabled.')

    change = PendingChange.objects.create(
        action_type=action_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        entity_repr=entity_repr[:255],
        original_values={k: _json_safe(v) for k, v in original_values.items()},
        proposed_values={k: _json_safe(v) for k, v in proposed_values.items()},
        reason=str(reason).strip(),
        status=PendingChange.STATUS_PENDING,
        made_by=request.user if request and getattr(request, 'user', None) else None,
        apply_payload=apply_payload or {},
        batch_id=batch_id or '',
    )
    _audit_pending(request, change, 'pending_submit')
    return change


def validate_before_approval(change: PendingChange, *, extreme_price_confirmed: bool = False) -> None:
    """Block approval that would cause imbalance unless explicitly confirmed."""
    if change.action_type == ACTION_PRODUCT_STOCK:
        proposed_qty = change.proposed_values.get('stock_quantity')
        if proposed_qty is not None:
            try:
                qty = int(proposed_qty)
            except (TypeError, ValueError):
                raise ValidationError('Invalid proposed stock quantity.')
            if qty < 0:
                raise ValidationError(
                    'Cannot approve negative stock level unless inventory rules allow it.'
                )

    if change.action_type == ACTION_PRODUCT_PRICE:
        old = change.original_values.get('price') or change.original_values.get('selling_price')
        new = change.proposed_values.get('price') or change.proposed_values.get('selling_price')
        if old is not None and new is not None:
            try:
                old_d = Decimal(str(old))
                new_d = Decimal(str(new))
                if old_d > 0:
                    ratio = abs(new_d - old_d) / old_d
                    if ratio > Decimal('0.5') and not extreme_price_confirmed:
                        raise ValidationError(
                            'Price change exceeds 50%; set extreme_price_confirmed=true to approve.'
                        )
            except (ArithmeticError, ValueError):
                pass

    if change.action_type in (ACTION_STOCK_ADJUST, ACTION_STOCK_PURCHASE):
        payload = change.apply_payload or {}
        qty = payload.get('quantity')
        if qty is not None and int(qty) < 0:
            product_id = payload.get('product_id')
            if product_id:
                Product = __import__('products.models', fromlist=['Product', 'ProductVariant']).Product
                ProductVariant = __import__(
                    'products.models', fromlist=['ProductVariant']
                ).ProductVariant
                product = Product.objects.get(pk=product_id)
                if product.track_stock:
                    from products.stock_utils import sellable_stock_quantity

                    variant = None
                    variant_id = payload.get('variant_id')
                    if variant_id:
                        variant = ProductVariant.objects.filter(
                            pk=variant_id, product=product
                        ).first()
                    after = sellable_stock_quantity(product, variant=variant) + int(qty)
                    if after < 0:
                        raise ValidationError(
                            'Approval would result in negative stock; adjust quantity or reject.'
                        )


@transaction.atomic
def approve_change(
    change: PendingChange,
    checker,
    request=None,
    *,
    extreme_price_confirmed: bool = False,
) -> PendingChange:
    if change.status != PendingChange.STATUS_PENDING:
        raise ValidationError('Only pending changes can be approved.')
    if not user_may_approve_change(checker, change):
        raise ValidationError('You are not allowed to approve this change.')

    if change.batch_id:
        batch = PendingChange.objects.filter(
            batch_id=change.batch_id,
            status=PendingChange.STATUS_PENDING,
        )
        for item in batch:
            validate_before_approval(item, extreme_price_confirmed=extreme_price_confirmed)
        for item in batch:
            _apply_single_change(item, checker, request)
        return change

    validate_before_approval(change, extreme_price_confirmed=extreme_price_confirmed)
    return _apply_single_change(change, checker, request)


def _apply_single_change(change: PendingChange, checker, request) -> PendingChange:
    from approvals.apply import apply_pending_change

    apply_pending_change(change)
    change.status = PendingChange.STATUS_APPROVED
    change.checked_by = checker
    change.checked_at = timezone.now()
    change.save(update_fields=['status', 'checked_by', 'checked_at'])
    if request:
        _audit_pending(
            request,
            change,
            'pending_approve',
            {'final_values': change.proposed_values},
        )
    return change


@transaction.atomic
def reject_change(
    change: PendingChange,
    checker,
    rejection_reason: str,
    request=None,
) -> PendingChange:
    if change.status != PendingChange.STATUS_PENDING:
        raise ValidationError('Only pending changes can be rejected.')
    if not user_may_approve_change(checker, change):
        raise ValidationError('You are not allowed to reject this change.')
    if not rejection_reason or not str(rejection_reason).strip():
        raise ValidationError({'rejection_reason': 'Rejection reason is required.'})

    now = timezone.now()
    if change.batch_id:
        batch = PendingChange.objects.filter(
            batch_id=change.batch_id,
            status=PendingChange.STATUS_PENDING,
        )
        for item in batch:
            item.status = PendingChange.STATUS_REJECTED
            item.checked_by = checker
            item.checked_at = now
            item.rejection_reason = str(rejection_reason).strip()
            item.save(update_fields=['status', 'checked_by', 'checked_at', 'rejection_reason'])
            if request:
                _audit_pending(request, item, 'pending_reject')
        return change

    change.status = PendingChange.STATUS_REJECTED
    change.checked_by = checker
    change.checked_at = now
    change.rejection_reason = str(rejection_reason).strip()
    change.save(update_fields=['status', 'checked_by', 'checked_at', 'rejection_reason'])
    if request:
        _audit_pending(request, change, 'pending_reject')
    return change


def route_product_sensitive_update(
    request,
    product,
    proposed: dict,
    *,
    reason: str,
) -> Optional[PendingChange]:
    """
    If maker-checker is on and payload touches sensitive fields, create pending row(s)
    and return the first change (caller must not mutate live product).
    """
    if not is_maker_checker_enabled():
        return None

    actions = classify_product_field_changes(proposed)
    if not actions:
        return None

    original = snapshot_model(
        product,
        fields=[k for k in proposed.keys() if hasattr(product, k)],
    )
    batch_id = str(uuid.uuid4()) if len(actions) > 1 else ''
    first = None
    for action_type in actions:
        slice_keys = _fields_for_action(action_type, proposed)
        if not slice_keys:
            continue
        ch = submit_change(
            request=request,
            action_type=action_type,
            entity_type='products.Product',
            entity_id=product.pk,
            entity_repr=str(product),
            original_values={k: original.get(k) for k in slice_keys},
            proposed_values={k: proposed[k] for k in slice_keys},
            reason=reason,
            batch_id=batch_id,
        )
        if first is None:
            first = ch
    return first


def route_variant_sensitive_update(
    request,
    variant,
    proposed: dict,
    *,
    reason: str,
) -> Optional[PendingChange]:
    if not is_maker_checker_enabled():
        return None

    actions = classify_variant_field_changes(proposed)
    if not actions:
        return None

    original = snapshot_model(
        variant,
        fields=[k for k in proposed.keys() if hasattr(variant, k)],
    )
    batch_id = str(uuid.uuid4()) if len(actions) > 1 else ''
    first = None
    for action_type in actions:
        slice_keys = _fields_for_action(action_type, proposed)
        if not slice_keys:
            continue
        ch = submit_change(
            request=request,
            action_type=action_type,
            entity_type='products.ProductVariant',
            entity_id=variant.pk,
            entity_repr=str(variant),
            original_values={k: original.get(k) for k in slice_keys},
            proposed_values={k: proposed[k] for k in slice_keys},
            reason=reason,
            batch_id=batch_id,
        )
        if first is None:
            first = ch
    return first


def _fields_for_action(action_type: str, proposed: dict) -> list[str]:
    from approvals.registry import (
        ACTION_PRODUCT_DEACTIVATE,
        ACTION_PRODUCT_PRICE,
        ACTION_PRODUCT_STOCK,
        ACTION_PRODUCT_TAX,
        ACTION_PRODUCT_UNIT,
        PRICE_FIELDS,
        STOCK_FIELDS,
    )

    if action_type == ACTION_PRODUCT_PRICE:
        return [k for k in proposed if k in PRICE_FIELDS and k != 'tax_rate']
    if action_type == ACTION_PRODUCT_TAX:
        return [k for k in proposed if k == 'tax_rate']
    if action_type == ACTION_PRODUCT_STOCK:
        return [k for k in proposed if k in STOCK_FIELDS]
    if action_type == ACTION_PRODUCT_DEACTIVATE:
        return ['is_active'] if 'is_active' in proposed else []
    if action_type == ACTION_PRODUCT_UNIT:
        return ['unit'] if 'unit' in proposed else []
    return list(proposed.keys())


def route_stock_movement(
    request,
    *,
    action_type: str,
    apply_payload: dict,
    reason: str,
    batch_id: str = '',
) -> Optional[PendingChange]:
    if not is_maker_checker_enabled():
        return None
    if is_emergency_stock_mode() and action_type == ACTION_STOCK_ADJUST:
        if int(apply_payload.get('quantity', 0)) > 0:
            return None

    product_id = apply_payload.get('product_id')
    variant_id = apply_payload.get('variant_id')
    Product = __import__('products.models', fromlist=['Product', 'ProductVariant']).Product
    ProductVariant = __import__('products.models', fromlist=['ProductVariant']).ProductVariant
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        from rest_framework.exceptions import ValidationError

        raise ValidationError({'product_id': 'Product not found'})

    entity_type = 'products.Product'
    entity_id = product.pk
    entity_repr = str(product)
    if variant_id:
        try:
            variant = ProductVariant.objects.get(pk=variant_id, product=product)
        except ProductVariant.DoesNotExist:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'variant_id': 'Variant not found for this product'})
        original_stock = variant.stock_quantity
        entity_type = 'products.ProductVariant'
        entity_id = variant.pk
        entity_repr = str(variant)
    else:
        original_stock = product.stock_quantity

    proposed_stock = original_stock
    qty = int(apply_payload.get('quantity', 0))
    if action_type == ACTION_STOCK_ADJUST:
        proposed_stock = original_stock + qty
    elif action_type == ACTION_STOCK_PURCHASE:
        proposed_stock = original_stock + abs(qty)
    elif action_type == ACTION_STOCK_TRANSFER:
        proposed_stock = max(0, original_stock - abs(qty))

    return submit_change(
        request=request,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_repr=entity_repr,
        original_values={'stock_quantity': original_stock},
        proposed_values={'stock_quantity': proposed_stock},
        reason=reason,
        apply_payload=apply_payload,
        batch_id=batch_id,
    )


@transaction.atomic
def route_bulk_stock_adjustments(
    request,
    *,
    adjustments: list[dict],
    reason: str,
) -> list[PendingChange]:
    """Queue one pending row per line; shared batch_id for atomic approve/reject."""
    import uuid

    from approvals.registry import ACTION_STOCK_ADJUST

    if not is_maker_checker_enabled():
        return []

    batch_id = str(uuid.uuid4())
    created: list[PendingChange] = []
    for adj in adjustments:
        product_id = adj.get('product_id')
        quantity = adj.get('quantity')
        notes = adj.get('notes', '')
        if product_id is None or quantity is None:
            continue
        change = route_stock_movement(
            request,
            action_type=ACTION_STOCK_ADJUST,
            apply_payload={
                'product_id': product_id,
                'variant_id': adj.get('variant_id'),
                'quantity': quantity,
                'notes': notes,
                'unit_cost': adj.get('unit_cost'),
                'branch_id': adj.get('branch_id'),
                'bulk': True,
            },
            reason=reason,
            batch_id=batch_id,
        )
        if change:
            created.append(change)
    return created
