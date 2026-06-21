from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from .access import user_may_view_all_daily_notes
from .models import DailyNote, DailyTask


def _author_display(user) -> str:
    first = user.first_name or ''
    last = user.last_name or ''
    name = f'{first} {last}'.strip()
    return name or user.username


class DailyNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = DailyNote
        fields = [
            'id',
            'note_date',
            'title',
            'content',
            'author',
            'author_name',
            'author_username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['author', 'created_at', 'updated_at']

    def get_author_name(self, obj):
        return _author_display(obj.author)


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
