from rest_framework.permissions import BasePermission

from payments.models import Subscription


class HasActiveSubscription(BasePermission):
    """Allow only users with an active subscription.

    Use it together with IsAuthenticated, so that anonymous users get 401
    and signed-in users without a subscription get 403.
    """

    # A dict message is returned as the body of the 403 response as is,
    # so the frontend can react to the machine-readable `code`
    message = {
        "detail": "An active subscription is required.",
        "code": "subscription_required",
    }

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and Subscription.objects.active().filter(user=user).exists()
        )
