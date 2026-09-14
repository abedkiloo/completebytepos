from django.contrib import admin

from .models import CustomerSite, SiteMedia


@admin.register(CustomerSite)
class CustomerSiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'label', 'customer', 'status', 'latitude', 'longitude', 'updated_at')
    list_filter = ('status', 'is_default')
    search_fields = ('label', 'landmark', 'customer__name')


@admin.register(SiteMedia)
class SiteMediaAdmin(admin.ModelAdmin):
    list_display = ('id', 'site', 'caption', 'created_at')
    search_fields = ('caption',)
