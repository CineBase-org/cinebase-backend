import logging

import stripe
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cinema_base.schema_errors import (
    NOT_FOUND,
    UNAUTHORIZED,
    SchemaErrorDetail,
)
from payments import services
from payments.models import Subscription
from payments.serializers import (
    CheckoutUrlSerializer,
    SubscriptionStatusSerializer,
)

logger = logging.getLogger(__name__)

CONFLICT = {
    409: OpenApiResponse(
        response=SchemaErrorDetail,
        description="The user already has an active subscription.",
    )
}

PROVIDER_ERRORS = {
    502: OpenApiResponse(
        response=SchemaErrorDetail,
        description="Stripe is unavailable. Try again later.",
    ),
    503: OpenApiResponse(
        response=SchemaErrorDetail,
        description="Payments are not configured on this server.",
    ),
}


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Start a subscription",
        description="Creates a Stripe Checkout page for the MoviePicker "
        "subscription and returns its URL.\n\n"
        "**How to use**\n"
        "1. Call this endpoint when the user clicks **Subscribe**. "
        "No request body is needed.\n"
        "2. Redirect the browser to the returned `url`.\n"
        "3. The user pays on the Stripe page and Stripe sends them back "
        "to the success or cancel page of the frontend.\n"
        "4. Payment is confirmed by Stripe on the server, which can take "
        "a few seconds. On the success page call "
        "`GET /api/payments/subscription/` until `is_active` is true.\n\n"
        "**Test mode.** Pay with the test card `4242 4242 4242 4242`, any "
        "future expiry date and any CVC.",
        request=None,
        responses={
            status.HTTP_200_OK: CheckoutUrlSerializer,
            **UNAUTHORIZED,
            **CONFLICT,
            **PROVIDER_ERRORS,
        },
    )
    def post(self, request):
        url = services.create_checkout_session(request.user)
        return Response({"url": url})


class PortalView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Manage the subscription",
        description="Creates a Stripe page where the user can cancel the "
        "subscription, change the card and see invoices, and returns its "
        "URL. Redirect the browser to it. After that, Stripe sends the "
        "user back to the frontend.\n\n"
        "Returns 404 if the user never subscribed. If the user cancels, "
        "access stays until the end of the paid period "
        "(see `cancel_at_period_end` in "
        "`GET /api/payments/subscription/`).",
        request=None,
        responses={
            status.HTTP_200_OK: CheckoutUrlSerializer,
            **UNAUTHORIZED,
            **NOT_FOUND,
            **PROVIDER_ERRORS,
        },
    )
    def post(self, request):
        url = services.create_portal_session(request.user)
        return Response({"url": url})


class SubscriptionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my subscription",
        description="Current subscription of the user. Use `is_active` to "
        "show or hide paid features (for example, the MoviePicker). "
        "If the user never subscribed, `is_active` is false and "
        "the other fields are null or false.",
        responses={
            status.HTTP_200_OK: SubscriptionStatusSerializer,
            **UNAUTHORIZED,
        },
    )
    def get(self, request):
        subscription = Subscription.objects.filter(user=request.user).first()
        data = {
            "is_active": bool(subscription and subscription.is_active),
            "status": subscription.status if subscription else None,
            "current_period_end": (
                subscription.current_period_end if subscription else None
            ),
            "cancel_at_period_end": bool(
                subscription and subscription.cancel_at_period_end
            ),
        }
        return Response(SubscriptionStatusSerializer(data).data)


class WebhookView(APIView):
    """Stripe calls this endpoint when a subscription changes.

    It has no token: the request is trusted only if its signature is valid.
    It is not shown in Swagger because the frontend never calls it.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def post(self, request):
        # The signature is calculated from the raw body: do not use
        # request.data here
        payload = request.body
        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = services.construct_event(payload, signature)
        except ValueError:
            return Response(
                {"detail": "Invalid payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.SignatureVerificationError:
            return Response(
                {"detail": "Invalid signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = services.handle_event(event)
        logger.info(
            "Stripe event %s (%s): %s", event["id"], event["type"], result
        )
        return Response({"status": result})
