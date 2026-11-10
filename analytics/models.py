import uuid

from django.conf import settings
from django.db import models


class DeviceType(models.TextChoices):
    MOBILE = "mobile", "Mobile"
    TABLET = "tablet", "Tablet"
    DESKTOP = "desktop", "Desktop"


class EventName(models.TextChoices):
    PAGE_VIEW = "page_view"
    CATALOG_VIEW = "catalog_view"
    FILTER_APPLY = "filter_apply"
    FILTER_RESET = "filter_reset"
    SORT_APPLY = "sort_apply"
    SEARCH_SUBMIT = "search_submit"
    MOVIE_CARD_CLICK = "movie_card_click"
    MOVIE_DETAILS_VIEW = "movie_details_view"
    WATCHLIST_ADD = "watchlist_add"
    WATCHLIST_REMOVE = "watchlist_remove"
    MOVIE_RATE = "movie_rate"
    COMMENT_CREATE = "comment_create"
    MOVIE_PICKER_USE = "movie_picker_use"


class Visitor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analytics_visitors",
    )
    first_seen_at = models.DateTimeField(auto_now_add=True)
    is_synthetic = models.BooleanField(default=False)

    def __str__(self):
        return f"Visitor {self.id}"


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor = models.ForeignKey(
        Visitor, on_delete=models.CASCADE, related_name="sessions"
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    device_type = models.CharField(
        max_length=20, choices=DeviceType.choices, null=True, blank=True
    )
    is_synthetic = models.BooleanField(default=False)

    def __str__(self):
        return f"Session {self.id}"


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="events"
    )
    event_name = models.CharField(max_length=100, choices=EventName.choices)
    event_timestamp = models.DateTimeField()
    page_path = models.CharField(max_length=255, null=True, blank=True)
    movie = models.ForeignKey(
        "movie.Movie",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analytics_events",
    )
    properties = models.JSONField(null=True, blank=True)
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["event_name", "event_timestamp"])]

    def __str__(self):
        return f"{self.event_name} at {self.event_timestamp}"
