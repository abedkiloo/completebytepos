"""
Income service layer - handles all income business logic
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, QuerySet
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime
from .models import IncomeCategory, Income
from settings.models import Branch
from settings.utils import get_current_branch, is_branch_support_enabled
from services.base import BaseService


class IncomeCategoryService(BaseService):
    """Service for income category operations"""
    
    def __init__(self):
        super().__init__(IncomeCategory)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for category listing.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
        
        Returns:
            QuerySet of categories with income_count annotation
        """
        queryset = self.model.objects.annotate(income_count=Count('incomes'))
        
        if not filters:
            return queryset
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        return queryset.order_by('name')


class IncomeService(BaseService):
    """Service for income operations"""
    
    def __init__(self):
        super().__init__(Income)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None, request=None) -> QuerySet:
        """
        Build queryset with filters for income listing.
        Moves query building logic from views to service layer.
        
        Args:
            filters: Dictionary with filter parameters:
                - branch_id: int (branch ID)
                - show_all: bool or str ('true'/'false')
                - category: int (category ID)
                - status: str (income status)
                - date_from: str (date string)
                - date_to: str (date string)
                - payment_method: str
            request: HttpRequest (optional, for branch detection)
        
        Returns:
            QuerySet of income records with proper select_related/prefetch_related
        """
        queryset = self.model.objects.all().select_related(
            'category', 'created_by', 'approved_by', 'branch'
        )
        
        if not filters:
            filters = {}
        
        # Handle branch filtering
        show_all = filters.get('show_all', 'false')
        if isinstance(show_all, str):
            show_all = show_all.lower() == 'true'
        
        if not show_all:
            branch_id = filters.get('branch_id')
            if not branch_id and request:
                current_branch = get_current_branch(request)
                if current_branch:
                    branch_id = current_branch.id
            
            if branch_id:
                try:
                    queryset = queryset.filter(branch_id=int(branch_id))
                except (ValueError, TypeError):
                    queryset = queryset.none()
        
        # Category filter
        category = filters.get('category')
        if category:
            try:
                queryset = queryset.filter(category_id=int(category))
            except (ValueError, TypeError):
                queryset = queryset.none()
        
        # Status filter
        status_filter = filters.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Date filters
        date_from = filters.get('date_from')
        if date_from:
            queryset = queryset.filter(income_date__gte=date_from)
        
        date_to = filters.get('date_to')
        if date_to:
            queryset = queryset.filter(income_date__lte=date_to)
        
        # Payment method filter
        payment_method = filters.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        
        return queryset.order_by('-income_date', '-created_at')
    
    @transaction.atomic
    def approve_income(self, income: Income, approved_by) -> Income:
        """Approve an income record and create journal entry"""
        if income.status == 'approved':
            raise ValidationError('Income is already approved')
        
        income.status = 'approved'
        income.approved_by = approved_by
        income.save()
        
        # Create journal entry for income
        try:
            from accounting.services import create_income_journal_entry
            create_income_journal_entry(income)
        except Exception as e:
            # Log error but don't fail the approval
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating journal entry for income: {e}")
        
        return income
    
    def get_income_statistics(self, branch: Optional[Branch] = None,
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive income statistics"""
        queryset = self.model.objects.all()
        
        if branch:
            queryset = queryset.filter(branch=branch)
        
        if date_from:
            queryset = queryset.filter(income_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(income_date__lte=date_to)
        
        today = timezone.now().date()
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))
        
        approved_queryset = queryset.filter(status='approved')
        
        total_income = approved_queryset.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        month_income = approved_queryset.filter(
            income_date__gte=start_of_month.date()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        by_category = list(approved_queryset.values(
            'category__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ))
        
        by_status = list(queryset.values('status').annotate(
            total=Sum('amount'),
            count=Count('id')
        ))
        
        return {
            'total_income': float(total_income),
            'month_income': float(month_income),
            'by_category': by_category,
            'by_status': by_status,
        }
