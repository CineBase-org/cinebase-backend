import time
from datetime import datetime, timezone as dt_timezone

from django.test import override_settings
from rest_framework import status

from payments.models import StripeEvent, Subscription
from payments.tests.helpers import (
    TEST_SETTINGS,
    BaseApiTestCase,
    create_subscription,
    make_event,
    sign,
)


@override_settings(**TEST_SETTINGS)
class WebhookTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = "/api/payments/webhook/"

    def send(self, payload, signature=None):
        if signature is None:
            signature = sign(payload)
        return self.client.post(
            self.url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

    # Signature and body checks

    def test_no_token_needed(self):
        res = self.send(make_event(user_id=self.user.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_missing_signature(self):
        res = self.client.post(
            self.url,
            data=make_event(user_id=self.user.pk),
            content_type="application/json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Subscription.objects.exists())

    def test_wrong_signature(self):
        payload = make_event(user_id=self.user.pk)

        res = self.send(payload, sign(payload, secret="whsec_other"))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Subscription.objects.exists())

    def test_body_changed_after_signing(self):
        payload = make_event(user_id=self.user.pk, status="active")
        signature = sign(payload)

        res = self.send(payload.replace("active", "trialing"), signature)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Subscription.objects.exists())

    def test_old_signature_is_rejected(self):
        payload = make_event(user_id=self.user.pk)
        old = sign(payload, timestamp=int(time.time()) - 3600)

        res = self.send(payload, old)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Subscription.objects.exists())

    def test_invalid_json(self):
        payload = "not json"

        res = self.send(payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(STRIPE_WEBHOOK_SECRET="")
    def test_not_configured_without_secret(self):
        res = self.send(make_event(user_id=self.user.pk), "t=1,v1=abc")

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    # Subscription events

    def test_created_saves_subscription(self):
        period_end = int(time.time()) + 1000

        res = self.send(
            make_event(
                "customer.subscription.created",
                user_id=self.user.pk,
                sub_id="sub_new",
                customer="cus_new",
                period_end=period_end,
            )
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {"status": "processed"})
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.stripe_subscription_id, "sub_new")
        self.assertEqual(subscription.stripe_customer_id, "cus_new")
        self.assertEqual(subscription.status, "active")
        self.assertFalse(subscription.cancel_at_period_end)
        self.assertEqual(
            subscription.current_period_end,
            datetime.fromtimestamp(period_end, tz=dt_timezone.utc),
        )
        self.assertTrue(subscription.is_active)

    def test_period_end_in_subscription_itself(self):
        """Older Stripe API versions keep the date in the subscription"""
        period_end = int(time.time()) + 500

        self.send(
            make_event(
                user_id=self.user.pk,
                period_end=period_end,
                period_end_in_items=False,
            )
        )

        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(
            subscription.current_period_end,
            datetime.fromtimestamp(period_end, tz=dt_timezone.utc),
        )

    def test_updated_changes_existing_subscription(self):
        now = int(time.time())
        self.send(
            make_event(
                event_id="evt_1", user_id=self.user.pk, created=now - 100
            )
        )

        self.send(
            make_event(
                event_id="evt_2",
                user_id=self.user.pk,
                status="past_due",
                cancel_at_period_end=True,
                created=now,
            )
        )

        self.assertEqual(Subscription.objects.count(), 1)
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.status, "past_due")
        self.assertTrue(subscription.cancel_at_period_end)
        self.assertFalse(subscription.is_active)

    def test_deleted_cancels_subscription(self):
        create_subscription(self.user)

        res = self.send(
            make_event(
                "customer.subscription.deleted",
                user_id=self.user.pk,
                status="canceled",
            )
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.status, "canceled")
        self.assertFalse(subscription.is_active)

    def test_user_found_by_customer_when_no_metadata(self):
        create_subscription(self.user, stripe_customer_id="cus_known")

        self.send(
            make_event(
                customer="cus_known", metadata={}, status="past_due"
            )
        )

        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.status, "past_due")

    def test_unknown_user_is_ignored(self):
        with self.assertLogs("payments.services", level="WARNING"):
            res = self.send(make_event(user_id=99999, metadata=None))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Subscription.objects.exists())

    def test_no_metadata_and_unknown_customer_is_ignored(self):
        with self.assertLogs("payments.services", level="WARNING"):
            res = self.send(make_event(metadata={}, customer="cus_stranger"))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Subscription.objects.exists())

    def test_bad_user_id_in_metadata_is_ignored(self):
        with self.assertLogs("payments.services", level="WARNING"):
            res = self.send(make_event(metadata={"user_id": "abc"}))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Subscription.objects.exists())

    # Repeated, old and unknown events

    def test_same_event_twice_is_applied_once(self):
        payload = make_event(user_id=self.user.pk, event_id="evt_same")
        self.send(payload)
        Subscription.objects.update(status="canceled")

        res = self.send(payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {"status": "duplicate"})
        self.assertEqual(StripeEvent.objects.count(), 1)
        # the second delivery did not touch the subscription
        self.assertEqual(
            Subscription.objects.get(user=self.user).status, "canceled"
        )

    def test_old_event_does_not_overwrite_newer_one(self):
        now = int(time.time())
        self.send(
            make_event(
                event_id="evt_new",
                user_id=self.user.pk,
                status="canceled",
                created=now,
            )
        )

        self.send(
            make_event(
                event_id="evt_old",
                user_id=self.user.pk,
                status="active",
                created=now - 60,
            )
        )

        self.assertEqual(
            Subscription.objects.get(user=self.user).status, "canceled"
        )

    def test_old_cancelled_subscription_does_not_replace_new_one(self):
        now = int(time.time())
        self.send(
            make_event(
                event_id="evt_new",
                user_id=self.user.pk,
                sub_id="sub_new",
                created=now - 100,
            )
        )

        self.send(
            make_event(
                "customer.subscription.deleted",
                event_id="evt_old_deleted",
                user_id=self.user.pk,
                sub_id="sub_old",
                status="canceled",
                created=now,
            )
        )

        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.stripe_subscription_id, "sub_new")
        self.assertEqual(subscription.status, "active")

    def test_new_subscription_replaces_old_one(self):
        now = int(time.time())
        create_subscription(
            self.user,
            stripe_subscription_id="sub_old",
            status=Subscription.Status.CANCELED,
        )

        self.send(
            make_event(
                "customer.subscription.created",
                user_id=self.user.pk,
                sub_id="sub_new",
                created=now,
            )
        )

        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.stripe_subscription_id, "sub_new")
        self.assertEqual(subscription.status, "active")

    def test_other_event_types_are_ignored(self):
        payload = make_event("invoice.paid", user_id=self.user.pk)

        res = self.send(payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {"status": "ignored"})
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(StripeEvent.objects.exists())
