from django.contrib import admin
from saas.models import StripeInfo, BillingEvent, StripeEvent

@admin.register(StripeInfo)
class StripeInfoAdmin(admin.ModelAdmin):
    ordering = ['-created_at']
    list_display = ['short_id', 'user', 'customer_id', 'subscription_id', 'subscription_end', 'created_at']


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    ordering = ['-created_at']
    list_display = ['short_id', 'event', 'created_at']

@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    ordering = ['-created_at']
    list_display = ['short_id', 'user', 'success', 'created_at']
