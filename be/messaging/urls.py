from django.urls import path

from . import views

urlpatterns = [
    path('reminders/debt/', views.debt_reminders, name='messaging-debt-reminders'),
    path(
        'reminders/debt/template/',
        views.debt_reminder_template,
        name='messaging-debt-reminder-template',
    ),
    path(
        'reminders/debt/preview/',
        views.debt_reminder_preview,
        name='messaging-debt-reminder-preview',
    ),
    path(
        'reminders/debt/send/',
        views.debt_reminder_send,
        name='messaging-debt-reminder-send',
    ),
]
