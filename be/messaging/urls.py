from django.urls import path

from . import views

urlpatterns = [
    path('templates/', views.sms_templates_list, name='messaging-templates-list'),
    path(
        'templates/<str:key>/',
        views.sms_template_detail,
        name='messaging-template-detail',
    ),
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
    path(
        'promos/customer-week/preview/',
        views.customer_week_preview,
        name='messaging-customer-week-preview',
    ),
    path(
        'promos/customer-week/send/',
        views.customer_week_send,
        name='messaging-customer-week-send',
    ),
    path(
        'blast/preview/',
        views.customer_blast_preview,
        name='messaging-customer-blast-preview',
    ),
    path(
        'blast/send/',
        views.customer_blast_send,
        name='messaging-customer-blast-send',
    ),
]
