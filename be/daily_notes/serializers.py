from django.utils import timezone
from rest_framework import serializers

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
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['author', 'completed_at', 'created_at', 'updated_at']

    def get_author_name(self, obj):
        return _author_display(obj.author)

    def validate(self, attrs):
        is_done = attrs.get('is_done')
        if is_done is None and self.instance:
            is_done = self.instance.is_done
        if is_done and not (attrs.get('title') or (self.instance and self.instance.title)):
            raise serializers.ValidationError({'title': 'Title is required.'})
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
        instance = DailyTask(**validated_data)
        if is_done:
            instance.mark_done(done=True, at=timezone.now())
        else:
            instance.is_done = False
            instance.completed_at = None
        instance.save()
        return instance

    def update(self, instance, validated_data):
        is_done = validated_data.pop('is_done', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if is_done is not None:
            self._apply_completion(instance, is_done)
        instance.save()
        return instance
