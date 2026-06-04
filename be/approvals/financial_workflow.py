"""
Maker-checker policy for records with their own approval status (expense, income, transfer).

When ``StoreSettings.maker_checker_enabled`` is on:
- Creates stay pending until a different user approves.
- ``proposal_reason`` is required on create/update.
- Makers cannot approve their own submissions (superuser exempt).
"""

from __future__ import annotations

from rest_framework.exceptions import ValidationError

from approvals.permissions import is_maker_checker_enabled

PROPOSAL_REASON_FIELD = 'proposal_reason'


def require_proposal_reason(request) -> str | None:
    if not is_maker_checker_enabled():
        return None
    data = getattr(request, 'data', None) or {}
    reason = str(data.get(PROPOSAL_REASON_FIELD) or '').strip()
    if not reason:
        raise ValidationError(
            {
                PROPOSAL_REASON_FIELD: (
                    'A reason is required when maker-checker is enabled.'
                ),
            }
        )
    return reason


def append_reason_to_notes(instance, reason: str | None) -> None:
    if not reason or not hasattr(instance, 'notes'):
        return
    prefix = f'[Maker-checker] {reason}'
    existing = (getattr(instance, 'notes', None) or '').strip()
    instance.notes = f'{prefix}\n{existing}' if existing else prefix


def apply_pending_status_on_create(instance) -> list[str]:
    """Force pending status when maker-checker is on. Returns fields to save."""
    if not is_maker_checker_enabled():
        return []
    if hasattr(instance, 'status'):
        instance.status = 'pending'
        return ['status']
    return []


def validate_checker_not_maker(approved_by, created_by_id) -> None:
    if not is_maker_checker_enabled():
        return
    if not created_by_id or not approved_by:
        return
    if created_by_id == approved_by.id and not getattr(approved_by, 'is_superuser', False):
        raise ValidationError(
            'You cannot approve your own submission when maker-checker is enabled.'
        )


def validate_locked_record_update(instance) -> None:
    """Block edits to finalized rows when maker-checker is on."""
    if not is_maker_checker_enabled():
        return
    status = getattr(instance, 'status', None)
    if status in ('approved', 'completed', 'paid'):
        raise ValidationError(
            'Approved records cannot be edited when maker-checker is enabled.'
        )


def finalize_financial_create(request, instance) -> None:
    """Apply MC rules immediately after create."""
    reason = require_proposal_reason(request)
    update_fields = apply_pending_status_on_create(instance)
    if reason:
        append_reason_to_notes(instance, reason)
        if hasattr(instance, 'notes'):
            update_fields.append('notes')
    if update_fields:
        instance.save(update_fields=list(dict.fromkeys(update_fields)))


def prepare_financial_update(request, instance) -> None:
    validate_locked_record_update(instance)
    reason = require_proposal_reason(request)
    if reason:
        append_reason_to_notes(instance, reason)
        instance.save(update_fields=['notes'])
