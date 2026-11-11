from django.urls import path

from analytics.views import TrackEventsView

urlpatterns = [
    path("events/", TrackEventsView.as_view(), name="track-events"),
]

app_name = "analytics"
