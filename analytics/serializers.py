import json

from rest_framework import serializers

from analytics.models import DeviceType, EventName

MAX_PROPERTIES_SIZE = 2048
MAX_EVENTS_PER_REQUEST = 50


class EventSerializer(serializers.Serializer):
    event_id = serializers.UUIDField(
        help_text="New UUID for every event. Sending the same event_id "
        "again does not create a duplicate."
    )
    event_name = serializers.ChoiceField(
        choices=EventName.choices, help_text="Name of the event."
    )
    event_timestamp = serializers.DateTimeField(
        help_text="When the event happened, ISO 8601 in UTC."
    )
    page_path = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        help_text="Page where the event happened, e.g. /catalog.",
    )
    movie_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="CineBase movie id (not TMDB). Unknown ids are "
        "stored as null.",
    )
    properties = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Extra details of the event as a JSON object, "
        "max 2 KB. No personal data.",
    )

    def validate_properties(self, value):
        if value is not None and len(json.dumps(value)) > MAX_PROPERTIES_SIZE:
            raise serializers.ValidationError("properties is too large")
        return value


class SessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(
        help_text="UUID of the visit. Create a new one after 30 minutes "
        "of inactivity."
    )
    started_at = serializers.DateTimeField(
        help_text="When the visit started, ISO 8601 in UTC."
    )
    device_type = serializers.ChoiceField(
        choices=DeviceType.choices,
        required=False,
        allow_null=True,
        help_text="Type of the device.",
    )


class TrackEventsSerializer(serializers.Serializer):
    visitor_id = serializers.UUIDField(
        help_text="UUID of the browser. Create it on the first visit and "
        "keep it in localStorage."
    )
    session = SessionSerializer(help_text="The current visit.")
    events = EventSerializer(
        many=True,
        allow_empty=False,
        max_length=MAX_EVENTS_PER_REQUEST,
        help_text="From 1 to 50 events of this visit.",
    )
