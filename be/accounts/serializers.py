from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, ModuleSettings, ModuleFeature, Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    module_display = serializers.CharField(source='get_module_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = Permission
        fields = [
            'id', 'module', 'action', 'name', 'description',
            'module_display', 'action_display', 'created_at'
        ]
        read_only_fields = ['created_at']


class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        source='permissions',
        write_only=True,
        required=False
    )
    permissions_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    
    def get_permissions_count(self, obj):
        try:
            if hasattr(obj, 'permissions'):
                return obj.permissions.count()
        except Exception:
            pass
        return 0
    
    def get_users_count(self, obj):
        try:
            if hasattr(obj, 'users'):
                return obj.users.count()
        except Exception:
            pass
        return 0
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'permissions', 'permission_ids',
            'is_system_role', 'is_active', 'permissions_count', 'users_count',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class RoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for role lists"""
    permissions_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    
    def get_permissions_count(self, obj):
        try:
            if hasattr(obj, 'permissions'):
                return obj.permissions.count()
        except Exception:
            pass
        return 0
    
    def get_users_count(self, obj):
        try:
            if hasattr(obj, 'users'):
                return obj.users.count()
        except Exception:
            pass
        return 0
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'is_system_role',
            'is_active', 'permissions_count', 'users_count'
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    is_super_admin = serializers.BooleanField(read_only=True)
    is_admin = serializers.BooleanField(read_only=True)
    is_manager = serializers.BooleanField(read_only=True)
    custom_role = RoleListSerializer(read_only=True, allow_null=True, required=False)
    custom_role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        source='custom_role',
        write_only=True,
        required=False,
        allow_null=True
    )
    role_display = serializers.CharField(source='get_role_display', read_only=True, allow_null=True, required=False)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'role', 'role_display', 'custom_role', 'custom_role_id',
            'phone_number', 'is_active',
            'is_super_admin', 'is_admin', 'is_manager',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True, allow_null=True, required=False)
    password = serializers.CharField(write_only=True, required=False)
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'password', 'is_staff', 'is_superuser', 'is_active',
            'date_joined', 'profile', 'permissions'
        ]
        read_only_fields = ['date_joined']
    
    def get_permissions(self, obj):
        """Get all permissions for this user"""
        try:
            if hasattr(obj, 'profile') and obj.profile:
                permissions = obj.profile.get_all_permissions()
                if permissions and hasattr(permissions, 'exists') and permissions.exists():
                    return PermissionSerializer(permissions, many=True).data
                elif permissions:
                    # If it's already a list/iterable
                    return PermissionSerializer(permissions, many=True).data
        except Exception as e:
            # Log error but don't fail
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting permissions for user {obj.id}: {e}")
        return []
    
    def create(self, validated_data):
        """Create user with password"""
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
    
    def update(self, instance, validated_data):
        """Update user, handling password separately"""
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users with profile"""
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(required=False, default='cashier')
    custom_role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        required=False,
        allow_null=True
    )
    phone_number = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'is_staff', 'is_active',
            'role', 'custom_role_id', 'phone_number'
        ]
    
    def create(self, validated_data):
        role = validated_data.pop('role', 'cashier')
        custom_role_id = validated_data.pop('custom_role_id', None)
        phone_number = validated_data.pop('phone_number', '')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        
        # Create profile
        profile_data = {
            'user': user,
            'role': role,
            'phone_number': phone_number,
            'created_by': self.context['request'].user
        }
        if custom_role_id:
            profile_data['custom_role'] = custom_role_id
        
        UserProfile.objects.create(**profile_data)
        
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


# Module settings serializers moved to settings app
# See settings/serializers.py for ModuleSettingsSerializer and ModuleFeatureSerializer
# Import for backward compatibility:
from settings.serializers import ModuleSettingsSerializer, ModuleFeatureSerializer
