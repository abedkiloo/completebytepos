from django.contrib import admin

from .models import DailyNote


@admin.register(DailyNote)
class DailyNoteAdmin(admin.ModelAdmin):
    list_display = ('note_date', 'title', 'author', 'created_at')
    list_filter = ('note_date',)
    search_fields = ('title', 'content', 'author__username')
    raw_id_fields = ('author',)
