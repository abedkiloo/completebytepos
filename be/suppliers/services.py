"""
Suppliers service layer — listing, search, and balance updates.

Public entry points:
    - ``SupplierService`` — queryset filters, search, balance, statistics

Balance updates run in a DB transaction. No ``AuditLog`` from this module.
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count, QuerySet
from django.core.exceptions import ValidationError
from .models import Supplier
from settings.models import ModuleSettings
from services.base import BaseService


class SupplierService(BaseService):
    """
    CRUD-adjacent operations for ``Supplier`` records.

    Attributes:
        model: Bound to ``Supplier``.
    """
    
    def __init__(self):
        super().__init__(Supplier)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for supplier listing.
        Moves query building logic from views to service layer.
        
        Args:
            filters: Dictionary with filter parameters:
                - is_active: bool or str ('true'/'false')
                - supplier_type: str
                - is_preferred: bool or str ('true'/'false')
                - search: str (search term)
        
        Returns:
            ``Supplier`` queryset ordered by ``name``. Invalid ``search`` returns
            ``queryset.none()`` rather than raising.
        """
        queryset = self.model.objects.all()
        
        if not filters:
            return queryset
        
        is_active = filters.get('is_active')
        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        supplier_type = filters.get('supplier_type')
        if supplier_type:
            queryset = queryset.filter(supplier_type=supplier_type)
        
        is_preferred = filters.get('is_preferred')
        if is_preferred is not None:
            if isinstance(is_preferred, str):
                is_preferred = is_preferred.lower() == 'true'
            queryset = queryset.filter(is_preferred=is_preferred)
        
        search = filters.get('search')
        if search:
            search = str(search).strip()
            if search:  # Only search if not empty after stripping
                try:
                    queryset = queryset.filter(
                        Q(name__icontains=search) |
                        Q(supplier_code__icontains=search) |
                        Q(email__icontains=search) |
                        Q(phone__icontains=search) |
                        Q(contact_person__icontains=search) |
                        Q(tax_id__icontains=search)
                    )
                except Exception:
                    # If search fails, return empty queryset rather than crashing
                    queryset = queryset.none()
        
        return queryset.order_by('name')
    
    def search_suppliers(self, query: str, limit: int = 50) -> List[Supplier]:
        """
        Search active suppliers by name, code, email, phone, or contact person.

        Args:
            query: Case-insensitive substring; blank or whitespace-only returns
                an empty list.
            limit: Max rows returned. Clamped to 1–1000; default 50 when ``< 1``.

        Returns:
            List of matching ``Supplier`` instances (``is_active=True`` only).
            On unexpected errors, logs and returns ``[]``.
        """
        try:
            if not query or not query.strip():
                return []
            
            # Validate and sanitize limit
            if limit < 1:
                limit = 50
            elif limit > 1000:
                limit = 1000
            
            queryset = self.model.objects.filter(
                Q(name__icontains=query) |
                Q(supplier_code__icontains=query) |
                Q(email__icontains=query) |
                Q(phone__icontains=query) |
                Q(contact_person__icontains=query)
            ).filter(is_active=True)[:limit]
            
            return list(queryset)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in search_suppliers: {e}", exc_info=True)
            return []  # Return empty list on error rather than raising
    
    @transaction.atomic
    def update_account_balance(self, supplier: Supplier, amount: Decimal,
                              transaction_type: str = 'credit',
                              reference: str = '', notes: str = '') -> Supplier:
        """
        Apply a credit or debit to ``supplier.account_balance``.

        Args:
            supplier: Existing ``Supplier`` row to mutate.
            amount: Non-negative ``Decimal`` (2 dp); sign comes from
                ``transaction_type``.
            transaction_type: ``'credit'`` increases balance owed; ``'debit'``
                decreases it. After debit, balance is floored at ``0``.
            reference: Unused legacy param (reserved for future ledger rows).
            notes: Unused legacy param (reserved for future ledger rows).

        Returns:
            The same ``supplier`` instance after ``save()``.

        Raises:
            ValidationError: When ``transaction_type`` is not ``credit`` or ``debit``.
        """
        if transaction_type == 'credit':
            supplier.account_balance += amount
        elif transaction_type == 'debit':
            supplier.account_balance -= amount
            if supplier.account_balance < 0:
                supplier.account_balance = Decimal('0')  # Don't allow negative
        else:
            raise ValidationError(f'Invalid transaction type: {transaction_type}')
        
        supplier.save()
        return supplier
    
    def get_supplier_statistics(self, supplier_id: int) -> Dict[str, Any]:
        """
        Snapshot stats for one supplier.

        Args:
            supplier_id: Primary key of the supplier.

        Returns:
            Dict with ``supplier_name``, balances, ``credit_available``,
            ``product_count``, ``rating``, ``is_preferred``. Money fields are
            ``float``.

        Raises:
            ValidationError: When no supplier exists for ``supplier_id``.
        """
        try:
            supplier = self.model.objects.get(id=supplier_id)
        except Supplier.DoesNotExist:
            raise ValidationError(f"Supplier with id {supplier_id} not found")
        
        # Get product count
        product_count = supplier.products.count()
        
        stats = {
            'supplier_name': supplier.name,
            'account_balance': float(supplier.account_balance),
            'credit_limit': float(supplier.credit_limit),
            'credit_available': float(supplier.credit_limit - supplier.account_balance) if supplier.credit_limit > 0 else 0,
            'product_count': product_count,
            'rating': supplier.rating,
            'is_preferred': supplier.is_preferred,
        }
        
        return stats
    
    def get_all_supplier_statistics(self) -> Dict[str, Any]:
        """
        Roll-up counts and balances for active suppliers only.

        Returns:
            Dict with ``total_suppliers``, ``preferred_suppliers``,
            ``total_account_balance`` (float), and ``by_type`` breakdown list.
        """
        queryset = self.model.objects.filter(is_active=True)
        
        total_suppliers = queryset.count()
        preferred_suppliers = queryset.filter(is_preferred=True).count()
        total_account_balance = queryset.aggregate(
            total=Sum('account_balance')
        )['total'] or Decimal('0')
        
        by_type = list(queryset.values('supplier_type').annotate(
            count=Count('id')
        ))
        
        return {
            'total_suppliers': total_suppliers,
            'preferred_suppliers': preferred_suppliers,
            'total_account_balance': float(total_account_balance),
            'by_type': by_type,
        }
