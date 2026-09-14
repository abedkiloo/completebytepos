from django.urls import path

from .views import public_invoice

urlpatterns = [
    path('invoices/<str:token>/', public_invoice, name='public-invoice'),
]
