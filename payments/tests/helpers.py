import hashlib
import hmac
import json
import time
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from payments.models import Subscription

# Fake values for tests: no real Stripe account is used
TEST_SETTINGS = {
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
    "STRIPE_PRICE_ID": "price_dummy",
    "STRIPE_SUCCESS_URL": "https://front.example/success",
    "STRIPE_CANCEL_URL": "https://front.example/cancel",
    "STRIPE_PORTAL_RETURN_URL": "https://front.example/profile",
}


class BaseApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()


def create_user(email="test@example.com", password="pass12345", **params):
    return get_user_model().objects.create_user(
        email=email, password=password, **params
    )


def create_subscription(user, **params):
    defaults = {
        "stripe_customer_id": "cus_1",
        "stripe_subscription_id": "sub_1",
        "status": Subscription.Status.ACTIVE,
        "current_period_end": timezone.now() + timedelta(days=30),
    }
    defaults.update(params)
    return Subscription.objects.create(user=user, **defaults)


def sign(payload, secret="whsec_dummy", timestamp=None):
    """Build the Stripe-Signature header the way Stripe does"""
    timestamp = int(time.time()) if timestamp is None else timestamp
    signed = f"{timestamp}.{payload}".encode()
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def make_event(
    event_type="customer.subscription.updated",
    event_id="evt_1",
    user_id=None,
    sub_id="sub_1",
    customer="cus_1",
    status="active",
    created=None,
    period_end=None,
    period_end_in_items=True,
    cancel_at_period_end=False,
    metadata=None,
):
    """A Stripe webhook body as a JSON string"""
    if period_end is None:
        period_end = int(time.time()) + 30 * 24 * 3600
    if metadata is None:
        metadata = {"user_id": str(user_id)} if user_id is not None else {}

    subscription = {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
        "metadata": metadata,
        "items": {
            "object": "list",
            "data": [
                {"id": "si_1", "current_period_end": period_end}
                if period_end_in_items
                else {"id": "si_1"}
            ],
        },
    }
    if not period_end_in_items:
        subscription["current_period_end"] = period_end

    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "created": int(time.time()) if created is None else created,
            "data": {"object": subscription},
        }
    )
