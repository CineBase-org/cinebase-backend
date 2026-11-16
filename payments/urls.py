from django.urls import path

from payments.views import (
    CheckoutView,
    PortalView,
    SubscriptionStatusView,
    WebhookView,
)

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("portal/", PortalView.as_view(), name="portal"),
    path("subscription/", SubscriptionStatusView.as_view(), name="status"),
    path("webhook/", WebhookView.as_view(), name="webhook"),
]

app_name = "payments"
