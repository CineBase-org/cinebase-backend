from django.contrib import admin

from payments.models import StripeEvent, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "current_period_end",
        "cancel_at_period_end",
        "stripe_subscription_id",
    )
    list_filter = ("status", "cancel_at_period_end")
    search_fields = (
        "user__email",
        "stripe_customer_id",
        "stripe_subscription_id",
    )
    # The source of truth is Stripe: do not edit it by hand
    readonly_fields = (
        "user",
        "stripe_customer_id",
        "stripe_subscription_id",
        "status",
        "current_period_end",
        "cancel_at_period_end",
        "last_event_at",
        "created_at",
        "updated_at",
    )


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "event_id", "created_at")
    list_filter = ("event_type",)
    search_fields = ("event_id",)
    readonly_fields = ("event_id", "event_type", "created_at")
