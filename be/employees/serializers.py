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
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    role_id = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    # Writable job role (login custom_role) — use this on create/update.
    job_role_id = serializers.IntegerField(
        required=False, allow_null=True, write_only=True
    )

    class Meta:
        model = Employee
        fields = [
            'id', 'user', 'user_username', 'user_email', 'role_id', 'role_name',
            'job_role_id',
            'employee_id', 'id_number', 'first_name', 'last_name',
            'full_name', 'email', 'phone', 'position', 'department', 'hire_date',
            'status', 'salary', 'bank_name', 'bank_account', 'tenant',
            'address', 'notes',
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

    def _profile(self, obj):
        if not obj.user_id:
            return None
        from accounts.models import UserProfile

        # Fresh fetch so role changes in the same request show up in the response.
        return (
            UserProfile.objects.select_related('custom_role')
            .filter(user_id=obj.user_id)
            .first()
        )

    def _role_from_position(self, obj):
        position = (obj.position or '').strip()
        if not position:
            return None
        from accounts.models import Role

        return Role.objects.filter(name__iexact=position, is_active=True).first()

    def get_role_id(self, obj):
        profile = self._profile(obj)
        if profile and profile.custom_role_id:
            return profile.custom_role_id
        role = self._role_from_position(obj)
        return role.id if role else None

    def get_role_name(self, obj):
        profile = self._profile(obj)
        if profile and profile.custom_role_id:
            return profile.custom_role.name
        role = self._role_from_position(obj)
        return role.name if role else None

    def get_user_email(self, obj):
        user = getattr(obj, 'user', None)
        if user and user.email:
            return user.email
        return ''

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

        attrs = validate_employee_write(attrs)
        # Accept job_role_id or legacy role_id from the client.
        raw = serializers.empty
        if 'job_role_id' in attrs:
            raw = attrs.pop('job_role_id')
        elif 'role_id' in self.initial_data and not isinstance(
            self.fields.get('role_id'), serializers.SerializerMethodField
        ):
            raw = self.initial_data.get('role_id')
        elif 'role_id' in self.initial_data:
            # SerializerMethodField is read-only; still accept body key for UX.
            raw = self.initial_data.get('role_id')

        if raw is not serializers.empty:
            if raw in ('', None):
                attrs['_role_id'] = None
            else:
                try:
                    role_pk = int(raw)
                except (TypeError, ValueError) as exc:
                    raise serializers.ValidationError(
                        {'job_role_id': 'Select a valid job role.'}
                    ) from exc
                from accounts.models import Role

                if not Role.objects.filter(pk=role_pk, is_active=True).exists():
                    raise serializers.ValidationError(
                        {'job_role_id': 'Role not found or inactive.'}
                    )
                attrs['_role_id'] = role_pk
        return attrs

    def _apply_role(self, employee, role_id):
        """Set the linked login user's job role (pay package inheritance)."""
        if employee.user_id is None:
            if role_id is not None:
                raise serializers.ValidationError(
                    {
                        'job_role_id': (
                            'Link a login user to this employee before assigning '
                            'a job role / pay package.'
                        )
                    }
                )
            return
        from accounts.models import Role, UserProfile

        profile, _ = UserProfile.objects.get_or_create(
            user_id=employee.user_id,
            defaults={'role': 'cashier', 'is_active': True},
        )
        if role_id is None:
            profile.custom_role_id = None
        else:
            profile.custom_role_id = role_id
        profile.save(update_fields=['custom_role_id'])

    def create(self, validated_data):
        validated_data.pop('job_role_id', None)
        role_id = validated_data.pop('_role_id', None)
        employee = super().create(validated_data)
        if role_id is not None:
            self._apply_role(employee, role_id)
        return employee

    def update(self, instance, validated_data):
        validated_data.pop('job_role_id', None)
        role_id = validated_data.pop('_role_id', serializers.empty)
        employee = super().update(instance, validated_data)
        if role_id is not serializers.empty:
            self._apply_role(employee, role_id)
        return employee

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

    def validate_user(self, value):
        if value is None:
            return value
        qs = Employee.objects.filter(user=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'This login user is already linked to another employee.'
            )
        return value


class FromUserEmployeeSerializer(serializers.Serializer):
    """Create an employee from an existing login user (basic pay only)."""

    user_id = serializers.IntegerField()
    employee_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    id_number = serializers.CharField(max_length=40, required=False, allow_blank=True, default='')
    email = serializers.EmailField(required=False, allow_blank=True)
    role_id = serializers.IntegerField(required=False, allow_null=True)
    position = serializers.CharField(max_length=100)
    department = serializers.ChoiceField(
        choices=Employee.DEPARTMENT_CHOICES, required=False, default='other'
    )
    hire_date = serializers.DateField()
    salary = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True, min_value=Decimal('0')
    )
    status = serializers.ChoiceField(
        choices=Employee.STATUS_CHOICES, required=False, default='active'
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_user_id(self, value):
        from django.contrib.auth.models import User

        try:
            user = User.objects.get(pk=value, is_active=True)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError('User not found or inactive.') from exc
        if Employee.objects.filter(user=user).exists():
            raise serializers.ValidationError('This user is already an employee.')
        self.context['linked_user'] = user
        return value

    def validate_employee_id(self, value):
        value = (value or '').strip()
        if value and Employee.objects.filter(employee_id=value).exists():
            raise serializers.ValidationError('An employee with this ID already exists.')
        return value

    def validate_role_id(self, value):
        if value is None:
            return value
        from accounts.models import Role

        if not Role.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError('Role not found or inactive.')
        return value

    def create(self, validated_data):
        from accounts.models import Role, UserProfile

        user = self.context['linked_user']
        emp_id = (validated_data.get('employee_id') or '').strip()
        if not emp_id:
            base = f'USR-{user.id}'
            emp_id = base
            n = 1
            while Employee.objects.filter(employee_id=emp_id).exists():
                n += 1
                emp_id = f'{base}-{n}'

        phone = ''
        try:
            phone = (user.profile.phone_number or '').strip()
        except Exception:
            phone = ''

        email = (validated_data.get('email') or user.email or '').strip()
        role_id = validated_data.get('role_id')
        position = validated_data['position'].strip()
        if role_id and not position:
            position = Role.objects.get(pk=role_id).name

        employee = Employee.objects.create(
            user=user,
            employee_id=emp_id,
            id_number=(validated_data.get('id_number') or '').strip(),
            first_name=(user.first_name or user.username or 'Staff')[:100],
            last_name=(user.last_name or 'User')[:100],
            email=email,
            phone=phone,
            position=position,
            department=validated_data.get('department') or 'other',
            hire_date=validated_data.get('hire_date'),
            status=validated_data.get('status') or 'active',
            salary=validated_data.get('salary'),
            notes=validated_data.get('notes') or '',
            created_by=self.context.get('request_user'),
        )
        if role_id is not None:
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': 'cashier', 'is_active': True},
            )
            profile.custom_role = Role.objects.get(pk=role_id)
            profile.save(update_fields=['custom_role'])
        return employee
