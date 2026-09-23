from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Role
from .access import user_may_view_all_daily_notes
from .models import DailyNote, DailyTask
from .services import create_notes_for_assignees, users_with_role
from utils.field_types import date_error_messages, raise_field_error, required_text_error


def _author_display(user) -> str:
    if user is None:
        return ''
    first = user.first_name or ''
    last = user.last_name or ''
    name = f'{first} {last}'.strip()
    return name or user.username


class DailyNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_username = serializers.CharField(source='author.username', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_username = serializers.SerializerMethodField()
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    assigned_role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    assigned_role_name = serializers.SerializerMethodField()
    created_count = serializers.SerializerMethodField()

    class Meta:
        model = DailyNote
        fields = [
            'id',
            'note_date',
            'title',
            'content',
            'is_sticky',
            'is_done',
            'completed_at',
            'author',
            'author_name',
            'author_username',
            'assigned_to',
            'assigned_to_name',
            'assigned_to_username',
            'assigned_role',
            'assigned_role_name',
            'assignment_group',
            'created_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'author',
            'completed_at',
            'assignment_group',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'note_date': {'error_messages': date_error_messages(label='note date')},
        }

    def validate_content(self, value):
        raise_field_error(
            required_text_error(
                value, label='note', example='Stock count completed at close of day', min_length=1
            )
        )
        return value.strip()

    def get_author_name(self, obj):
        return _author_display(obj.author)

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to_id:
            return ''
        return _author_display(obj.assigned_to)

    def get_assigned_to_username(self, obj):
        if not obj.assigned_to_id:
            return ''
        return obj.assigned_to.username

    def get_assigned_role_name(self, obj):
        role = getattr(obj, 'assigned_role', None)
        return role.name if role is not None else ''

    def get_created_count(self, obj):
        return getattr(self, '_created_count', 1)

    def validate(self, attrs):
        request = self.context.get('request')
        is_sticky = attrs.get('is_sticky')
        if is_sticky is None and self.instance:
            is_sticky = self.instance.is_sticky
        is_sticky = bool(is_sticky)

        assigned_to = attrs.get('assigned_to', serializers.empty)
        if assigned_to is serializers.empty:
            assigned_to = self.instance.assigned_to if self.instance else None

        assigned_role = attrs.get('assigned_role', serializers.empty)
        if assigned_role is serializers.empty:
            assigned_role = self.instance.assigned_role if self.instance else None

        if assigned_to and assigned_role and not self.instance:
            raise serializers.ValidationError(
                {'assigned_role': 'Choose a person or a role, not both.'}
            )

        may_assign_others = bool(
            request and user_may_view_all_daily_notes(getattr(request, 'user', None))
        )

        if assigned_role and not may_assign_others:
            raise serializers.ValidationError(
                {'assigned_role': 'You can only assign notes to yourself.'}
            )

        if assigned_role and assigned_to is None and not self.instance:
            if not users_with_role(assigned_role):
                raise serializers.ValidationError(
                    {'assigned_role': 'No active staff have that role.'}
                )

        if (
            is_sticky
            and assigned_to is None
            and assigned_role is None
            and request
            and getattr(request, 'user', None)
            and not may_assign_others
        ):
            assigned_to = request.user
            attrs['assigned_to'] = assigned_to

        if is_sticky and assigned_to is None and assigned_role is None:
            raise serializers.ValidationError(
                {
                    'assigned_to': (
                        'Assign this sticky note to a person or a role.'
                        if may_assign_others
                        else 'Assign this sticky note to the person who must resolve it.'
                    )
                }
            )

        if request and assigned_to and assigned_to.id != request.user.id:
            if not may_assign_others:
                raise serializers.ValidationError(
                    {'assigned_to': 'You can only assign sticky notes to yourself.'}
                )

        is_done = attrs.get('is_done')
        if is_done is None and self.instance:
            is_done = self.instance.is_done
        if is_done and not (attrs.get('content') or (self.instance and self.instance.content)):
            raise serializers.ValidationError({'content': 'Write the note before ticking it.'})
        return attrs

    def _apply_completion(self, instance, is_done: bool):
        if is_done and not instance.is_done:
            instance.mark_done(done=True, at=timezone.now())
        elif not is_done and instance.is_done:
            instance.mark_done(done=False)
        else:
            instance.is_done = is_done

    def create(self, validated_data):
        is_done = validated_data.pop('is_done', False)
        assigned_to = validated_data.pop('assigned_to', None)
        assigned_role = validated_data.pop('assigned_role', None)
        notes = create_notes_for_assignees(
            author=validated_data['author'],
            note_date=validated_data['note_date'],
            content=validated_data['content'],
            title=validated_data.get('title', ''),
            is_sticky=validated_data.get('is_sticky', False),
            is_done=is_done,
            assigned_to=assigned_to,
            assigned_role=assigned_role,
        )
        if not notes:
            raise serializers.ValidationError(
                {'assigned_role': 'No active staff have that role.'}
            )
        self._created_count = len(notes)
        return notes[0]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not getattr(self, '_created_count', None):
            data.pop('created_count', None)
        return data

    def update(self, instance, validated_data):
        is_done = validated_data.pop('is_done', None)
        assigned_to = validated_data.pop('assigned_to', serializers.empty)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if assigned_to is not serializers.empty:
            instance.assigned_to = assigned_to
        assigned_role = validated_data.get('assigned_role', serializers.empty)
        if assigned_role is not serializers.empty:
            instance.assigned_role = assigned_role
        if instance.is_sticky and instance.assigned_to_id is None and instance.assigned_role_id is None:
            instance.assigned_to = instance.author
        if is_done is not None:
            self._apply_completion(instance, is_done)
        instance.save()
        return instance


class DailyTaskSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_username = serializers.CharField(source='author.username', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = DailyTask
        fields = [
            'id',
            'task_date',
            'title',
            'description',
            'is_done',
            'completed_at',
            'author',
            'author_name',
            'author_username',
            'assigned_to',
            'assigned_to_name',
            'assigned_to_username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['author', 'completed_at', 'created_at', 'updated_at']
        extra_kwargs = {
            'task_date': {'error_messages': date_error_messages(label='task date')},
        }

    def validate_title(self, value):
        raise_field_error(
            required_text_error(
                value, label='task title', example='Restock sugar 2kg', min_length=1
            )
        )
        return value.strip()

    def get_author_name(self, obj):
        return _author_display(obj.author)

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to_id:
            return ''
        return _author_display(obj.assigned_to)

    def validate(self, attrs):
        is_done = attrs.get('is_done')
        if is_done is None and self.instance:
            is_done = self.instance.is_done
        if is_done and not (attrs.get('title') or (self.instance and self.instance.title)):
            raise serializers.ValidationError({'title': 'Title is required.'})

        request = self.context.get('request')
        assigned_to = attrs.get('assigned_to')
        if assigned_to is None and self.instance:
            assigned_to = self.instance.assigned_to

        if request and assigned_to and assigned_to.id != request.user.id:
            if not user_may_view_all_daily_notes(request.user):
                raise serializers.ValidationError(
                    {'assigned_to': 'You can only assign tasks to yourself.'}
                )

        return attrs

    def _apply_completion(self, instance, is_done: bool):
        if is_done and not instance.is_done:
            instance.mark_done(done=True, at=timezone.now())
        elif not is_done and instance.is_done:
            instance.mark_done(done=False)
        else:
            instance.is_done = is_done

    def create(self, validated_data):
        is_done = validated_data.pop('is_done', False)
        assigned_to = validated_data.pop('assigned_to', None)
        author = validated_data['author']
        if assigned_to is None:
            assigned_to = author
        instance = DailyTask(**validated_data, assigned_to=assigned_to)
        if is_done:
            instance.mark_done(done=True, at=timezone.now())
        else:
            instance.is_done = False
            instance.completed_at = None
        instance.save()
        return instance

    def update(self, instance, validated_data):
        is_done = validated_data.pop('is_done', None)
        assigned_to = validated_data.pop('assigned_to', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if assigned_to is not None:
            instance.assigned_to = assigned_to
        if is_done is not None:
            self._apply_completion(instance, is_done)
        instance.save()
        return instance
