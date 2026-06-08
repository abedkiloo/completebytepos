from rest_framework import serializers

from .models import DailyNote


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
        first = obj.author.first_name or ''
        last = obj.author.last_name or ''
        name = f'{first} {last}'.strip()
        return name or obj.author.username
