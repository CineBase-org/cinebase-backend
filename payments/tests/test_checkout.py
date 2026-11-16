from types import SimpleNamespace
from unittest import mock

import stripe
from django.test import override_settings
from rest_framework import status

from payments.models import Subscription
from payments.tests.helpers import (
    TEST_SETTINGS,
    BaseApiTestCase,
    create_subscription,
)

CREATE = "stripe.checkout.Session.create"


@override_settings(**TEST_SETTINGS)
class CheckoutTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = "/api/payments/checkout/"
        self.client.force_authenticate(self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @mock.patch(CREATE)
    def test_returns_checkout_url(self, create):
        create.return_value = SimpleNamespace(url="https://stripe.test/pay")

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {"url": "https://stripe.test/pay"})

    @mock.patch(CREATE)
    def test_session_params_for_new_customer(self, create):
        create.return_value = SimpleNamespace(url="https://stripe.test/pay")

        self.client.post(self.url)

        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["api_key"], "sk_test_dummy")
        self.assertEqual(kwargs["mode"], "subscription")
        self.assertEqual(
            kwargs["line_items"], [{"price": "price_dummy", "quantity": 1}]
        )
        self.assertEqual(kwargs["success_url"], "https://front.example/success")
        self.assertEqual(kwargs["cancel_url"], "https://front.example/cancel")
        self.assertEqual(kwargs["client_reference_id"], str(self.user.pk))
        self.assertEqual(
            kwargs["subscription_data"],
            {"metadata": {"user_id": str(self.user.pk)}},
        )
        self.assertEqual(kwargs["customer_email"], self.user.email)
        self.assertNotIn("customer", kwargs)

    @mock.patch(CREATE)
    def test_reuses_stripe_customer_after_cancel(self, create):
        create_subscription(
            self.user,
            status=Subscription.Status.CANCELED,
            stripe_customer_id="cus_old",
        )
        create.return_value = SimpleNamespace(url="https://stripe.test/pay")

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["customer"], "cus_old")
        self.assertNotIn("customer_email", kwargs)

    @mock.patch(CREATE)
    def test_already_subscribed(self, create):
        create_subscription(self.user)

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("detail", res.data)
        create.assert_not_called()

    @mock.patch(CREATE, side_effect=stripe.StripeError("boom"))
    def test_stripe_error(self, create):
        with self.assertLogs("payments.services", level="ERROR"):
            res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("detail", res.data)

    @override_settings(STRIPE_SECRET_KEY="")
    @mock.patch(CREATE)
    def test_not_configured_without_key(self, create):
        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        create.assert_not_called()

    @override_settings(STRIPE_PRICE_ID="")
    @mock.patch(CREATE)
    def test_not_configured_without_price(self, create):
        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        create.assert_not_called()
