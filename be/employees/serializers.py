from rest_framework import serializers
from decimal import Decimal

from utils.field_types import (
    NAME_EXAMPLE,
    date_error_messages,
    email_error,
    email_error_messages,
    money_error_messages,
    raise_field_error,
    required_text_error,
)
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
        extra_kwargs = {
            'email': {
                'required': False,
                'allow_blank': True,
                'error_messages': email_error_messages(),
            },
            'hire_date': {'error_messages': date_error_messages(label='hire date')},
            'salary': {
                'min_value': Decimal('0'),
                'required': False,
                'allow_null': True,
                'error_messages': money_error_messages(allow_zero=True),
            },
        }

    def get_created_by_username(self, obj):
        if obj.created_by:
            return obj.created_by.username
        return None

    def validate_first_name(self, value):
        raise_field_error(
            required_text_error(value, label='first name', example=NAME_EXAMPLE, min_length=1)
        )
        return value.strip()

    def validate_last_name(self, value):
        raise_field_error(
            required_text_error(value, label='last name', example='Wambua', min_length=1)
        )
        return value.strip()

    def validate_email(self, value):
        raise_field_error(email_error(value))
        return (value or '').strip() if value else value

    def validate(self, attrs):
        from employees.module_settings import validate_employee_write

        return validate_employee_write(attrs)

    def to_representation(self, instance):
        from employees.module_settings import apply_employee_representation_flags

        return apply_employee_representation_flags(super().to_representation(instance))

    def validate_phone(self, value):
        from utils.phone import validate_optional_phone

        return validate_optional_phone(value)

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
