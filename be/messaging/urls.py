from django.urls import path

from .views import debt_reminders

urlpatterns = [
    path('reminders/debt/', debt_reminders, name='messaging-debt-reminders'),
]
