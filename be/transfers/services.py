"""
Transfers service layer - handles all money transfer business logic
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, QuerySet
from django.core.exceptions import ValidationError
from .models import MoneyTransfer
from services.base import BaseService


class MoneyTransferService(BaseService):
    """Service for money transfer operations"""
    
    def __init__(self):
        super().__init__(MoneyTransfer)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for transfer listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - status: str (transfer status)
                - date_from: str (date string)
                - date_to: str (date string)
                - transfer_type: str
                - account: int (account ID - matches from or to)
        
        Returns:
            QuerySet of transfers with proper select_related
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
        """Approve and complete a transfer"""
        if transfer.status == 'completed':
            raise ValidationError('Transfer is already completed')
        
        transfer.status = 'completed'
        transfer.approved_by = approved_by
        transfer.save()
        
        return transfer
    
    def get_transfer_statistics(self) -> Dict[str, Any]:
        """Get comprehensive transfer statistics"""
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
