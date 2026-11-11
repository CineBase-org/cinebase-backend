from django.db import transaction
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    inline_serializer,
    OpenApiExample,
)
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.authentication import OptionalJWTAuthentication
from analytics.models import Event, Session, Visitor
from analytics.serializers import TrackEventsSerializer
from analytics.throttles import AnalyticsRateThrottle
from cinema_base.schema_errors import BAD_REQUEST
from movie.models import Movie

TRACK_EVENTS_DESCRIPTION = (
    "Send user activity events for product analytics. The client collects "
    "events and sends them in batches.\n\n"
    "**How to use**\n"
    "1. Create `visitor_id` (UUID) on the first visit, keep it in the "
    "browser (localStorage) and send it with every request.\n"
    "2. Create `session_id` (UUID) for a visit. Start a new session after "
    "30 minutes of inactivity.\n"
    "3. Create a new `event_id` (UUID) for every event.\n"
    "4. Send up to 50 events per request: every few seconds and when the "
    "page is closed (`navigator.sendBeacon`).\n\n"
    "**Authentication.** Optional. Send `Authorization: Bearer <access>` "
    "when the user is logged in: the visitor is linked to the user, "
    "including the events sent before the login. An invalid or expired "
    "token is ignored, so this endpoint never returns 401.\n\n"
    "**Good to know**\n"
    "- Sending the same `event_id` again does not create a duplicate, so "
    "retries are safe.\n"
    "- An unknown `movie_id` is stored as `null`.\n"
    "- A `session_id` cannot be used by another `visitor_id` (400).\n"
    "- Limit: 60 requests per minute from one IP (429).\n"
    "- Tracking must never break the UI: ignore errors and do not show "
    "them to the user.\n\n"
    "**Events and recommended `properties`**\n"
    "- `page_view`: any page opened.\n"
    "- `catalog_view`: catalog page opened.\n"
    "- `filter_apply`: filters applied. `genres` (list of ids), "
    "`min_rating`, `year_from`, `year_to`.\n"
    "- `filter_reset`: filters reset.\n"
    "- `sort_apply`: sorting changed. `sort_by`.\n"
    "- `search_submit`: search submitted. `query_length` (do not send the "
    "text itself).\n"
    "- `movie_card_click`: a movie card clicked. Send `movie_id`.\n"
    "- `movie_details_view`: movie page opened. Send `movie_id`.\n"
    "- `movie_picker_use`: random movie picker used. The same filters as "
    "in GET /api/movies/random/, and `movie_id` of the result.\n"
    "- `watchlist_add`, `watchlist_remove`: a movie added to or removed "
    "from the watchlist. Send `movie_id`, and only after the request "
    "succeeded.\n"
    "- `movie_rate`: a movie rated. Send `movie_id` and `score`.\n"
    "- `comment_create`: a comment added. Send `movie_id` and "
    "`is_reply` (true or false)."
)

TRACK_EVENTS_EXAMPLE = {
    "visitor_id": "11111111-1111-4111-8111-111111111111",
    "session": {
        "session_id": "22222222-2222-4222-8222-222222222222",
        "started_at": "2026-11-10T11:30:00Z",
        "device_type": "mobile",
    },
    "events": [
        {
            "event_id": "33333333-3333-4333-8333-333333333333",
            "event_name": "page_view",
            "event_timestamp": "2026-11-10T11:30:05Z",
            "page_path": "/catalog",
            "movie_id": None,
            "properties": {},
        },
        {
            "event_id": "44444444-4444-4444-8444-444444444444",
            "event_name": "filter_apply",
            "event_timestamp": "2026-11-10T11:30:20Z",
            "page_path": "/catalog",
            "movie_id": None,
            "properties": {"genres": [28, 12], "min_rating": 7},
        },
        {
            "event_id": "55555555-5555-4555-8555-555555555555",
            "event_name": "movie_card_click",
            "event_timestamp": "2026-11-10T11:30:40Z",
            "page_path": "/catalog",
            "movie_id": 1,
            "properties": {},
        },
    ],
}


class TrackEventsView(APIView):
    authentication_classes = (OptionalJWTAuthentication,)
    permission_classes = (AllowAny,)
    throttle_classes = (AnalyticsRateThrottle,)

    @extend_schema(
        summary="Track user activity events",
        description=TRACK_EVENTS_DESCRIPTION,
        auth=[{}, {"jwtAuth": []}],
        request=TrackEventsSerializer,
        examples=[
            OpenApiExample(
                "Browsing the catalog",
                value=TRACK_EVENTS_EXAMPLE,
                request_only=True,
            ),
            OpenApiExample(
                "Accepted",
                value={"accepted": 3},
                response_only=True,
                status_codes=["201"],
            ),
        ],
        responses={
            status.HTTP_201_CREATED: inline_serializer(
                name="TrackEventsAccepted",
                fields={"accepted": serializers.IntegerField()},
            ),
            **BAD_REQUEST,
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="Too many requests, retry later"
            ),
        },
    )
    def post(self, request):
        serializer = TrackEventsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        session_data = data["session"]
        events_data = data["events"]

        with transaction.atomic():
            visitor, _ = Visitor.objects.get_or_create(id=data["visitor_id"])
            if request.user.is_authenticated and visitor.user_id is None:
                visitor.user = request.user
                visitor.save(update_fields=["user"])

            session, _ = Session.objects.get_or_create(
                id=session_data["session_id"],
                defaults={
                    "visitor": visitor,
                    "started_at": session_data["started_at"],
                    "device_type": session_data.get("device_type"),
                },
            )
            if session.visitor_id != visitor.id:
                raise ValidationError(
                    {"session": ["Session belongs to another visitor."]}
                )

            movie_ids = {
                event["movie_id"]
                for event in events_data
                if event.get("movie_id") is not None
            }
            known_movie_ids = set(
                Movie.objects.filter(id__in=movie_ids).values_list(
                    "id", flat=True
                )
            )

            Event.objects.bulk_create(
                [
                    Event(
                        id=event["event_id"],
                        session=session,
                        event_name=event["event_name"],
                        event_timestamp=event["event_timestamp"],
                        page_path=event.get("page_path"),
                        movie_id=(
                            event["movie_id"]
                            if event.get("movie_id") in known_movie_ids
                            else None
                        ),
                        properties=event.get("properties"),
                    )
                    for event in events_data
                ],
                ignore_conflicts=True,
            )

        return Response(
            {"accepted": len(events_data)}, status=status.HTTP_201_CREATED
        )
