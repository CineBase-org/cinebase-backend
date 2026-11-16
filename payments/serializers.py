from rest_framework import serializers


class CheckoutUrlSerializer(serializers.Serializer):
    url = serializers.URLField(
        read_only=True,
        help_text="Stripe page to redirect the user to (open it in the "
        "same tab)",
    )


class SubscriptionStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(
        read_only=True,
        help_text="True if the user has access to paid features right now",
    )
    status = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text="Stripe status: active, trialing, past_due, unpaid, "
        "canceled, incomplete, incomplete_expired, paused. "
        "null if the user never subscribed",
    )
    current_period_end = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
        help_text="When the paid period ends. If cancel_at_period_end is "
        "true, this is the last day of access",
    )
    cancel_at_period_end = serializers.BooleanField(
        read_only=True,
        help_text="True if the user cancelled: access stays until "
        "current_period_end and the subscription will not renew",
    )
