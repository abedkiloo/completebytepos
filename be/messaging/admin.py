from django.contrib import admin

from .models import MessageOutbox

admin.site.register(MessageOutbox)
