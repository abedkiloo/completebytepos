from django.contrib import admin

from .models import (
    DeliveryLineResult,
    DeliveryRoute,
    DeliveryStop,
    ProofOfDelivery,
    ProposedPinCorrection,
)


@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ('id', 'route_date', 'delivery_agent')


@admin.register(DeliveryStop)
class DeliveryStopAdmin(admin.ModelAdmin):
    list_display = ('id', 'route', 'sequence', 'status', 'field_order')


admin.site.register(DeliveryLineResult)
admin.site.register(ProofOfDelivery)
admin.site.register(ProposedPinCorrection)
