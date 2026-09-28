from django.contrib import admin

from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'is_featured', 'published_at', 'updated_at')
    list_filter = ('status', 'is_featured')
    search_fields = ('title', 'excerpt', 'body', 'tags')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at')
