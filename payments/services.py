"""Work with Stripe: sessions for the frontend and webhook processing.

All calls to Stripe are made here, so views stay thin and tests can mock
a few functions.
"""

import logging
from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from payments.exceptions import (
    AlreadySubscribed,
    NoSubscription,
    PaymentProviderError,
    PaymentsNotConfigured,
)
from payments.models import StripeEvent, Subscription

logger = logging.getLogger(__name__)

# Statuses after which a subscription is over for good
FINISHED_STATUSES = (
    Subscription.Status.CANCELED,
    Subscription.Status.INCOMPLETE_EXPIRED,
)

HANDLED_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


def _api_key():
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentsNotConfigured()
    return settings.STRIPE_SECRET_KEY


def create_checkout_session(user):
    """Create a Stripe Checkout page for a new subscription, return its URL"""
    api_key = _api_key()
    if not settings.STRIPE_PRICE_ID:
        raise PaymentsNotConfigured()

    if Subscription.objects.active().filter(user=user).exists():
        raise AlreadySubscribed()

    params = {
        "mode": "subscription",
        "line_items": [{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        "success_url": settings.STRIPE_SUCCESS_URL,
        "cancel_url": settings.STRIPE_CANCEL_URL,
        "client_reference_id": str(user.pk),
        # The metadata is copied to the subscription, so every subscription
        # webhook tells us which user it belongs to
        "subscription_data": {"metadata": {"user_id": str(user.pk)}},
    }
    previous = Subscription.objects.filter(user=user).first()
    if previous:
        # Reuse the Stripe customer of a user who subscribes again
        params["customer"] = previous.stripe_customer_id
    else:
        params["customer_email"] = user.email

    try:
        session = stripe.checkout.Session.create(api_key=api_key, **params)
    except stripe.StripeError:
        logger.exception("Stripe: could not create a checkout session")
        raise PaymentProviderError()
    return session.url


def create_portal_session(user):
    """Create a Stripe page where the user manages the subscription"""
    api_key = _api_key()
    subscription = Subscription.objects.filter(user=user).first()
    if subscription is None:
        raise NoSubscription()

    try:
        session = stripe.billing_portal.Session.create(
            api_key=api_key,
            customer=subscription.stripe_customer_id,
            return_url=settings.STRIPE_PORTAL_RETURN_URL,
        )
    except stripe.StripeError:
        logger.exception("Stripe: could not create a portal session")
        raise PaymentProviderError()
    return session.url


def construct_event(payload, signature):
    """Check the signature of a webhook and return the event as a dict.

    Raises ValueError for a broken body and
    stripe.SignatureVerificationError for a wrong signature.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise PaymentsNotConfigured()
    event = stripe.Webhook.construct_event(
        payload, signature, settings.STRIPE_WEBHOOK_SECRET
    )
    # Stripe objects are not dicts (no .get()): use plain dicts from here on
    return event.to_dict()


@transaction.atomic
def handle_event(event):
    """Apply a verified webhook event. Return what happened to it:
    "processed", "duplicate" or "ignored".
    """
    if event["type"] not in HANDLED_EVENTS:
        return "ignored"

    _, created = StripeEvent.objects.get_or_create(
        event_id=event["id"], defaults={"event_type": event["type"]}
    )
    if not created:
        return "duplicate"

    # If this fails, the transaction is rolled back together with the
    # StripeEvent row, so Stripe will send the event again
    sync_subscription(event["data"]["object"], event["created"])
    return "processed"


def sync_subscription(data, event_created):
    """Save the state of a Stripe subscription for its user"""
    user = _find_user(data)
    if user is None:
        logger.warning(
            "Stripe subscription %s does not belong to any user",
            data.get("id"),
        )
        return

    event_at = datetime.fromtimestamp(event_created, tz=dt_timezone.utc)
    subscription_id = data["id"]
    existing = (
        Subscription.objects.select_for_update().filter(user=user).first()
    )
    if existing:
        if existing.last_event_at and existing.last_event_at > event_at:
            return  # an old event came after a newer one
        if (
            existing.stripe_subscription_id != subscription_id
            and data["status"] in FINISHED_STATUSES
        ):
            return  # an old finished subscription must not replace the new

    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "stripe_customer_id": data["customer"],
            "stripe_subscription_id": subscription_id,
            "status": data["status"],
            "current_period_end": _period_end(data),
            "cancel_at_period_end": bool(data.get("cancel_at_period_end")),
            "last_event_at": event_at,
        },
    )


def _find_user(data):
    user_id = (data.get("metadata") or {}).get("user_id")
    if user_id and str(user_id).isdigit():
        user = get_user_model().objects.filter(pk=int(user_id)).first()
        if user:
            return user

    customer = data.get("customer")
    if customer:
        known = (
            Subscription.objects.select_related("user")
            .filter(stripe_customer_id=customer)
            .first()
        )
        if known:
            return known.user
    return None


def _period_end(data):
    """End of the paid period as a datetime, or None if Stripe did not send it.

    Newer Stripe API versions keep it in the subscription items, older ones
    in the subscription itself.
    """
    items = (data.get("items") or {}).get("data") or []
    timestamps = [
        item.get("current_period_end")
        for item in items
        if item.get("current_period_end")
    ]
    timestamp = max(timestamps) if timestamps else None
    if timestamp is None:
        timestamp = data.get("current_period_end")
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)
