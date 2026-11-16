from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

import stripe
from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from payments.models import Subscription
from payments.tests.helpers import (
    TEST_SETTINGS,
    BaseApiTestCase,
    create_subscription,
)

CREATE_PORTAL = "stripe.billing_portal.Session.create"


@override_settings(**TEST_SETTINGS)
class PortalTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = "/api/payments/portal/"
        self.client.force_authenticate(self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @mock.patch(CREATE_PORTAL)
    def test_no_subscription(self, create):
        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", res.data)
        create.assert_not_called()

    @mock.patch(CREATE_PORTAL)
    def test_returns_portal_url(self, create):
        create_subscription(self.user, stripe_customer_id="cus_42")
        create.return_value = SimpleNamespace(url="https://stripe.test/portal")

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {"url": "https://stripe.test/portal"})
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["customer"], "cus_42")
        self.assertEqual(kwargs["return_url"], "https://front.example/profile")

    @mock.patch(CREATE_PORTAL, side_effect=stripe.StripeError("boom"))
    def test_stripe_error(self, create):
        create_subscription(self.user)

        with self.assertLogs("payments.services", level="ERROR"):
            res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)


class SubscriptionStatusTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = "/api/payments/subscription/"
        self.client.force_authenticate(self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)

        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_never_subscribed(self):
        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data,
            {
                "is_active": False,
                "status": None,
                "current_period_end": None,
                "cancel_at_period_end": False,
            },
        )

    def test_active(self):
        create_subscription(self.user)

        res = self.client.get(self.url)

        self.assertTrue(res.data["is_active"])
        self.assertEqual(res.data["status"], "active")
        self.assertIsNotNone(res.data["current_period_end"])
        self.assertFalse(res.data["cancel_at_period_end"])

    def test_cancelled_but_paid_period_not_over(self):
        create_subscription(self.user, cancel_at_period_end=True)

        res = self.client.get(self.url)

        self.assertTrue(res.data["is_active"])
        self.assertTrue(res.data["cancel_at_period_end"])

    def test_period_over(self):
        create_subscription(
            self.user, current_period_end=timezone.now() - timedelta(minutes=1)
        )

        res = self.client.get(self.url)

        self.assertFalse(res.data["is_active"])

    def test_not_active_statuses(self):
        for value in (
            Subscription.Status.PAST_DUE,
            Subscription.Status.UNPAID,
            Subscription.Status.CANCELED,
            Subscription.Status.INCOMPLETE,
            Subscription.Status.PAUSED,
        ):
            with self.subTest(status=value):
                Subscription.objects.all().delete()
                create_subscription(self.user, status=value)

                res = self.client.get(self.url)

                self.assertFalse(res.data["is_active"])
                self.assertEqual(res.data["status"], value)

    def test_trialing_is_active(self):
        create_subscription(self.user, status=Subscription.Status.TRIALING)

        res = self.client.get(self.url)

        self.assertTrue(res.data["is_active"])
