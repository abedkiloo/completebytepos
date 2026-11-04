"""
Money transfer listing, approval workflow, and statistics.

Public entry points:
    - ``MoneyTransferService.build_queryset``
    - ``MoneyTransferService.approve_transfer`` / ``reject_transfer`` / ``resubmit_transfer``
    - ``MoneyTransferService.get_transfer_statistics``

Side effects: approve sets ``completed`` and triggers balance refresh on save;
reject sets ``cancelled`` and notifies via daily notes. Checker/maker rules from
``approvals.financial_workflow``.
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, QuerySet
from django.core.exceptions import ValidationError
from .models import MoneyTransfer
from services.base import BaseService


class MoneyTransferService(BaseService):
    """
    Transfer queries and approval lifecycle (complete / return / resubmit).

    Attributes:
        model: Bound to ``MoneyTransfer``.
    """

    def __init__(self):
        super().__init__(MoneyTransfer)

    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build transfer list queryset with status, date, type, and account filters.

        Args:
            filters: Optional dict. Supported keys:
                status: exact status string.
                date_from / date_to: inclusive ``transfer_date`` bounds.
                transfer_type: exact type code.
                account: bank account PK; matches ``from_account`` OR ``to_account``.

        Returns:
            ``QuerySet`` with ``select_related`` on accounts and users;
            ordered by ``-transfer_date``, ``-created_at``. Invalid account id → empty.
        """
        queryset = self.model.objects.all().select_related(
            'from_account', 'to_account', 'created_by', 'approved_by'
        )

        if not filters:
            return queryset.order_by('-transfer_date', '-created_at')

        status_filter = filters.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(transfer_date__gte=date_from)

        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(transfer_date__lte=date_to)

        transfer_type = filters.get('transfer_type')
        if transfer_type:
            queryset = queryset.filter(transfer_type=transfer_type)

        account = filters.get('account')
        if account:
            try:
                account_id = int(account)
                queryset = queryset.filter(
                    Q(from_account_id=account_id) | Q(to_account_id=account_id)
                )
            except (ValueError, TypeError):
                queryset = queryset.none()

        return queryset.order_by('-transfer_date', '-created_at')

    @transaction.atomic
    def approve_transfer(self, transfer: 'MoneyTransfer', approved_by) -> 'MoneyTransfer':
        """
        Complete a pending transfer after checker validation.

        Args:
            transfer: Must not already be ``completed``.
            approved_by: Checker user stored on ``approved_by``.

        Returns:
            Updated ``MoneyTransfer`` with status ``completed``.

        Raises:
            ValidationError: Already completed, or checker/maker or date rules fail.

        Side effects:
            Saves transfer (model ``save`` updates bank balances); clears rejection notices.
        """
        from approvals.financial_workflow import (
            validate_checker_not_maker,
            validate_past_dated_checker,
        )

        validate_checker_not_maker(approved_by, transfer.created_by_id)
        validate_past_dated_checker(approved_by, transfer.transfer_date, transfer.created_at)
        if transfer.status == 'completed':
            raise ValidationError('Transfer is already completed')

        transfer.status = 'completed'
        transfer.approved_by = approved_by
        transfer.save()
        from daily_notes.approval_notice import SOURCE_TRANSFER, complete_rejection_notices

        complete_rejection_notices(source=SOURCE_TRANSFER, record_id=transfer.id)

        return transfer

    @transaction.atomic
    def reject_transfer(self, transfer: 'MoneyTransfer', rejected_by, reason: str) -> 'MoneyTransfer':
        """
        Cancel a pending transfer and return it to the requester with reason.

        Args:
            transfer: Must be ``pending``.
            rejected_by: Checker user.
            reason: Non-blank string after strip.

        Returns:
            Updated transfer with status ``cancelled``.

        Raises:
            ValidationError: Empty reason, wrong status, or workflow validation.

        Side effects:
            Appends note; notifies requester; does not mutate bank balances.
        """
        from approvals.financial_workflow import (
            validate_checker_not_maker,
            validate_past_dated_checker,
        )
        from daily_notes.approval_notice import SOURCE_TRANSFER, notify_approval_rejected

        validate_checker_not_maker(rejected_by, transfer.created_by_id)
        validate_past_dated_checker(rejected_by, transfer.transfer_date, transfer.created_at)
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError({'rejection_reason': 'Say why you are returning this transfer.'})
        if transfer.status != 'pending':
            raise ValidationError('Only pending transfers can be returned to the requester.')
        transfer.status = 'cancelled'
        note = f'[Rejected by {getattr(rejected_by, "username", "checker")}] {reason}'
        transfer.notes = f'{transfer.notes}\n{note}'.strip() if transfer.notes else note
        transfer.save(update_fields=['status', 'notes', 'updated_at'])
        notify_approval_rejected(
            requester=transfer.created_by,
            checker=rejected_by,
            action_type='transfer',
            entity_repr=transfer.transfer_number or transfer.description,
            rejection_reason=reason,
            source=SOURCE_TRANSFER,
            record_id=transfer.id,
        )
        return transfer

    @transaction.atomic
    def resubmit_transfer(self, transfer: 'MoneyTransfer', user) -> 'MoneyTransfer':
        """
        Move a cancelled (returned) transfer back to pending.

        Args:
            transfer: Must be ``cancelled``.
            user: Must be ``created_by`` unless superuser.

        Returns:
            Updated transfer with status ``pending``.

        Raises:
            ValidationError: Wrong status or not owner.

        Side effects:
            Clears rejection notices for this transfer id.
        """
        if transfer.status != 'cancelled':
            raise ValidationError('Only returned transfers can be sent back for approval.')
        if (
            transfer.created_by_id
            and transfer.created_by_id != getattr(user, 'id', None)
            and not getattr(user, 'is_superuser', False)
        ):
            raise ValidationError('You can only resubmit your own transfers.')
        transfer.status = 'pending'
        transfer.save(update_fields=['status', 'updated_at'])
        from daily_notes.approval_notice import SOURCE_TRANSFER, complete_rejection_notices

        complete_rejection_notices(source=SOURCE_TRANSFER, record_id=transfer.id)
        return transfer

    def get_transfer_statistics(self) -> Dict[str, Any]:
        """
        Aggregate completed transfer volume and counts by type and status.

        Returns:
            Dict with ``total_transferred`` (float, completed only),
            ``by_type`` and ``by_status`` (lists of dicts with ``total`` and ``count``).
            No rows → ``total_transferred`` is 0.0.
        """
        completed_queryset = self.model.objects.filter(status='completed')

        total_transferred = completed_queryset.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        by_type = list(completed_queryset.values('transfer_type').annotate(
            total=Sum('amount'),
            count=Count('id')
        ))

        by_status = list(self.model.objects.values('status').annotate(
            total=Sum('amount'),
            count=Count('id')
        ))

        return {
            'total_transferred': float(total_transferred),
            'by_type': by_type,
            'by_status': by_status,
        }
