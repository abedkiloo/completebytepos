"""
Employees service layer - handles all employee business logic
"""
from typing import Optional, List, Dict, Any
from django.db.models import Q, Count, QuerySet
from .models import Employee
from accounts.permissions import HasModuleAccess
from services.base import BaseService


class EmployeeService(BaseService):
    """Service for employee operations"""
    
    def __init__(self):
        super().__init__(Employee)
    
    def build_queryset(self, filters: Optional[Dict[str, Any]] = None) -> QuerySet:
        """
        Build queryset with filters for employee listing.
        Moves query building logic from views to service layer.
        
        Args:
            filters: Dictionary with filter parameters:
                - search: str (search term)
                - status: str (employee status)
                - department: str (department name)
        
        Returns:
            QuerySet of employees
        """
        queryset = self.model.objects.all()
        
        if not filters:
            return queryset.order_by('-created_at')
        
        search = filters.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(email__icontains=search) |
                Q(position__icontains=search)
            )
        
        status_filter = filters.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        department = filters.get('department')
        if department:
            queryset = queryset.filter(department=department)
        
        return queryset.order_by('-created_at')
    
    def get_employee_statistics(self, queryset: Optional[QuerySet] = None) -> Dict[str, Any]:
        """Get comprehensive employee statistics"""
        if queryset is None:
            queryset = self.model.objects.all()
        
        total_employees = queryset.count()
        active_employees = queryset.filter(status='active').count()
        inactive_employees = queryset.filter(status='inactive').count()
        
        # Employees by department
        employees_by_department = list(
            queryset.values('department')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Employees by status
        employees_by_status = list(
            queryset.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        return {
            'total_employees': total_employees,
            'active_employees': active_employees,
            'inactive_employees': inactive_employees,
            'employees_by_department': employees_by_department,
            'employees_by_status': employees_by_status,
        }
