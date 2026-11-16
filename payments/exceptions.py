from rest_framework import status
from rest_framework.exceptions import APIException


class PaymentsNotConfigured(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Payments are not configured."
    default_code = "payments_not_configured"


class PaymentProviderError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Payment provider is unavailable. Try again later."
    default_code = "payment_provider_error"


class AlreadySubscribed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "You already have an active subscription."
    default_code = "already_subscribed"


class NoSubscription(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "You do not have a subscription yet."
    default_code = "no_subscription"
