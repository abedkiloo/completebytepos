from django.contrib import admin

from .models import DailyNote, DailyTask


@admin.register(DailyNote)
class DailyNoteAdmin(admin.ModelAdmin):
    list_display = ('note_date', 'title', 'author', 'created_at')
    list_filter = ('note_date',)
    search_fields = ('title', 'content', 'author__username')
    raw_id_fields = ('author',)


@admin.register(DailyTask)
class DailyTaskAdmin(admin.ModelAdmin):
    list_display = ('task_date', 'title', 'is_done', 'assigned_to', 'author', 'completed_at')
    list_filter = ('task_date', 'is_done')
    search_fields = ('title', 'description', 'author__username', 'assigned_to__username')
    raw_id_fields = ('author', 'assigned_to')
