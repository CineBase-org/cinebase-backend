from django.conf import settings
from django.db import models
from django.utils import timezone


class SubscriptionQuerySet(models.QuerySet):
    def active(self):
        """Subscriptions that give access to paid features right now"""
        return self.filter(status__in=Subscription.ACCESS_STATUSES).filter(
            models.Q(current_period_end__isnull=True)
            | models.Q(current_period_end__gt=timezone.now())
        )


class Subscription(models.Model):
    """Subscription of a user, kept in sync with Stripe via webhooks"""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIALING = "trialing", "Trialing"
        PAST_DUE = "past_due", "Past due"
        UNPAID = "unpaid", "Unpaid"
        CANCELED = "canceled", "Canceled"
        INCOMPLETE = "incomplete", "Incomplete"
        INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete expired"
        PAUSED = "paused", "Paused"

    # Only these statuses give access to paid features
    ACCESS_STATUSES = (Status.ACTIVE, Status.TRIALING)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    stripe_customer_id = models.CharField(max_length=255, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=32, choices=Status.choices)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    # Time of the last Stripe event we applied: protects from old events
    # that arrive after newer ones
    last_event_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SubscriptionQuerySet.as_manager()

    def __str__(self):
        return f"Subscription {self.stripe_subscription_id} ({self.status})"

    @property
    def is_active(self):
        if self.status not in self.ACCESS_STATUSES:
            return False
        return (
            self.current_period_end is None
            or self.current_period_end > timezone.now()
        )


class StripeEvent(models.Model):
    """Processed Stripe webhook events: Stripe can send one event twice"""

    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} {self.event_id}"
