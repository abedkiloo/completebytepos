from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum
from accounts.permissions import HasPermission, HasModuleAccess
from .models import Employee
from .serializers import EmployeeSerializer
from .services import EmployeeService
from utils.audit_helpers import audited_perform_create
from utils.audit_mixin import AuditedModelViewSetMixin
from employees.module_settings import (
    employees_enable_create,
    employees_enable_edit,
    employees_enable_delete,
    employees_enable_statistics,
)


class EmployeeViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet for Employee Management
    """
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    audit_module = 'employees'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee_service = EmployeeService()
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated(), HasModuleAccess('employees')]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), HasModuleAccess('employees'), HasPermission('employees', 'create')]
        return super().get_permissions()
    
    def get_queryset(self):
        """Get queryset using service layer - all query logic moved to service"""
        # Check if employees module is enabled
        if not HasModuleAccess('employees').has_permission(self.request, self):
            return Employee.objects.none()
        
        filters = {}
        query_params = self.request.query_params
        
        # Extract all filter parameters
        for param in ['search', 'status', 'department']:
            if param in query_params:
                filters[param] = query_params.get(param)
        
        return self.employee_service.build_queryset(filters)

    @staticmethod
    def _feature_disabled_response(feature_label: str):
        return Response(
            {'error': f'{feature_label} is disabled in store settings.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    def perform_create(self, serializer):
        audited_perform_create(self, serializer, created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        if not employees_enable_create():
            return self._feature_disabled_response('Creating employees')
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not employees_enable_edit():
            return self._feature_disabled_response('Editing employees')
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not employees_enable_edit():
            return self._feature_disabled_response('Editing employees')
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not employees_enable_delete():
            return self._feature_disabled_response('Deleting employees')
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get employee statistics - thin view, business logic in service"""
        if not employees_enable_statistics():
            return self._feature_disabled_response('Employee statistics')
        try:
            queryset = self.get_queryset()
            stats = self.employee_service.get_employee_statistics(queryset)
            return Response(stats)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
