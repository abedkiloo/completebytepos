"""
Suppliers service layer - handles all supplier business logic
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
    """Service for supplier operations"""
    
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
            QuerySet of suppliers
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
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(supplier_code__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(contact_person__icontains=search) |
                Q(tax_id__icontains=search)
            )
        
        return queryset.order_by('name')
    
    def search_suppliers(self, query: str, limit: int = 50) -> List[Supplier]:
        """Search suppliers by name, code, email, phone, or contact person"""
        if not query or not query.strip():
            return []
        
        queryset = self.model.objects.filter(
            Q(name__icontains=query) |
            Q(supplier_code__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(contact_person__icontains=query)
        ).filter(is_active=True)[:limit]
        
        return list(queryset)
    
    @transaction.atomic
    def update_account_balance(self, supplier: Supplier, amount: Decimal,
                              transaction_type: str = 'credit',
                              reference: str = '', notes: str = '') -> Supplier:
        """
        Update supplier account balance.
        transaction_type: 'credit' (increase balance/owed) or 'debit' (decrease balance/paid)
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
        """Get comprehensive statistics for a supplier"""
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
        """Get aggregate statistics for all suppliers"""
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
