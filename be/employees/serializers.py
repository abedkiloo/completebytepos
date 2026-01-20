from rest_framework import serializers
from .models import Employee


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for Employee model"""
    full_name = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    created_by_username = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'first_name', 'last_name', 'full_name',
            'email', 'phone', 'position', 'department', 'hire_date',
            'status', 'salary', 'address', 'notes',
            'created_by', 'created_by_username', 'created_at', 'updated_at',
            'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_created_by_username(self, obj):
        if obj.created_by:
            return obj.created_by.username
        return None
    
    def validate_employee_id(self, value):
        """Ensure employee_id is unique"""
        if self.instance:
            # Update: check if another employee has this ID
            if Employee.objects.filter(employee_id=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("An employee with this ID already exists.")
        else:
            # Create: check if employee_id exists
            if Employee.objects.filter(employee_id=value).exists():
                raise serializers.ValidationError("An employee with this ID already exists.")
        return value
