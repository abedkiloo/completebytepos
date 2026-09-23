"""Create Delivery Driver users from the field-sales / dispatch board."""

from __future__ import annotations

import re
import secrets

from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from accounts.models import Role, UserProfile
from accounts.password_policy import MIN_PASSWORD_LENGTH, validate_new_password
from accounts.role_definitions import ROLE_DELIVERY_AGENT, sync_default_roles
from utils.phone import PhoneNumberError, normalize_phone_number


def split_display_name(value: str) -> tuple[str, str]:
    parts = [p for p in (value or '').strip().split() if p]
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0][:150], ''
    return parts[0][:150], ' '.join(parts[1:])[:150]


def slug_username(value: str) -> str:
    cleaned = re.sub(r'[^a-z0-9._-]', '', (value or '').strip().lower())
    return cleaned[:40] or 'driver'


def unique_username(base: str) -> str:
    candidate = slug_username(base)
    n = 1
    while User.objects.filter(username=candidate).exists():
        n += 1
        suffix = str(n)
        stem = slug_username(base)[: max(1, 40 - len(suffix))]
        candidate = f'{stem}{suffix}'
    return candidate


def generate_temp_password() -> str:
    password = secrets.token_urlsafe(9)
    while validate_new_password(password) is not None:
        password = secrets.token_urlsafe(10)
    return password


def delivery_driver_role() -> Role:
    role = Role.objects.filter(name=ROLE_DELIVERY_AGENT, is_active=True).first()
    if role is None:
        sync_default_roles()
        role = Role.objects.filter(name=ROLE_DELIVERY_AGENT, is_active=True).first()
    if role is None:
        raise serializers.ValidationError(
            {'detail': 'Delivery Driver role is not configured.'}
        )
    return role


def driver_payload(user: User, *, temporary_password: str | None = None) -> dict:
    full = f'{user.first_name} {user.last_name}'.strip()
    profile = getattr(user, 'profile', None)
    data = {
        'id': user.id,
        'username': user.username,
        'display_name': full or user.username,
        'phone_number': getattr(profile, 'phone_number', '') or '',
    }
    if temporary_password:
        data['temporary_password'] = temporary_password
    return data


class CreateDriverSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=150, allow_blank=True)
    phone = serializers.CharField(max_length=20)
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate_display_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError(
                'Enter the driver’s name, e.g. Jane Wambua'
            )
        return name

    def validate_phone(self, value):
        try:
            return normalize_phone_number(value, required=True)
        except PhoneNumberError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_username(self, value):
        raw = (value or '').strip()
        if not raw:
            return ''
        slug = slug_username(raw)
        if User.objects.filter(username=slug).exists():
            raise serializers.ValidationError('That username is already taken.')
        return slug

    def validate_password(self, value):
        raw = (value or '').strip()
        if not raw:
            return ''
        error = validate_new_password(raw)
        if error:
            raise serializers.ValidationError(
                error.replace('new_password is required', 'Password is required')
            )
        return raw

    def create(self, validated_data):
        display_name = validated_data['display_name']
        phone = validated_data['phone']
        username = validated_data.get('username') or unique_username(f'drv{phone[-9:]}')
        password = validated_data.get('password') or generate_temp_password()
        first_name, last_name = split_display_name(display_name)
        request = self.context.get('request')
        created_by = getattr(request, 'user', None) if request else None
        role = delivery_driver_role()

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            UserProfile.objects.create(
                user=user,
                role='cashier',
                custom_role=role,
                phone_number=phone,
                is_active=True,
                must_change_password=True,
                created_by=created_by if getattr(created_by, 'is_authenticated', False) else None,
            )
        user._temporary_password = password
        return user


# Keep policy import used so generated passwords always meet min length.
assert MIN_PASSWORD_LENGTH >= 6
