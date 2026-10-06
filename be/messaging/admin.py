from django.contrib import admin

from .models import MessageOutbox, SmsTemplate

admin.site.register(MessageOutbox)
admin.site.register(SmsTemplate)
