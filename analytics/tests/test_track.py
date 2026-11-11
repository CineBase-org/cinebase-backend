import uuid
from unittest import mock

from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from analytics.models import Event, Session, Visitor
from analytics.tests.helpers import BaseApiTestCase, make_body, make_event
from movie.models import Movie


class TrackEventsTests(BaseApiTestCase):
    def test_track_anonymous(self):
        res = self.track(make_body([make_event(), make_event()]))

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data, {"accepted": 2})
        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(Event.objects.count(), 2)
        self.assertIsNone(Visitor.objects.get().user)

    def test_track_saves_event_fields(self):
        body = make_body(
            [
                make_event(
                    event_name="filter_apply",
                    page_path="/catalog",
                    properties={"genres": [1, 2]},
                )
            ],
            device_type="tablet",
        )

        self.track(body)

        event = Event.objects.get()
        self.assertEqual(event.event_name, "filter_apply")
        self.assertEqual(event.page_path, "/catalog")
        self.assertEqual(event.properties, {"genres": [1, 2]})
        self.assertEqual(event.session.device_type, "tablet")

    def test_track_same_event_twice_is_not_duplicated(self):
        body = make_body()

        self.track(body)
        res = self.track(body)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(Event.objects.count(), 1)

    def test_track_same_visitor_new_session(self):
        visitor_id = str(uuid.uuid4())

        self.track(make_body(visitor_id=visitor_id))
        self.track(make_body(visitor_id=visitor_id))

        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Session.objects.count(), 2)

    def test_track_session_of_another_visitor_rejected(self):
        session_id = str(uuid.uuid4())
        self.track(make_body(session_id=session_id))

        res = self.track(make_body(session_id=session_id))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session", res.data)
        self.assertEqual(Event.objects.count(), 1)

    def test_track_known_and_unknown_movie(self):
        movie = Movie.objects.create(tmdb_id=1, title="Movie")
        body = make_body(
            [make_event(movie_id=movie.id), make_event(movie_id=999999)]
        )

        self.track(body)

        movie_ids = set(Event.objects.values_list("movie_id", flat=True))
        self.assertEqual(movie_ids, {movie.id, None})


class TrackEventsAuthTests(BaseApiTestCase):
    def test_track_authenticated_links_user(self):
        self.client.force_authenticate(user=self.user)

        self.track(make_body())

        self.assertEqual(Visitor.objects.get().user, self.user)

    def test_track_with_valid_token_links_user(self):
        token = str(RefreshToken.for_user(self.user).access_token)

        self.track(make_body(), HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(Visitor.objects.get().user, self.user)

    def test_track_with_invalid_token_is_anonymous_not_401(self):
        res = self.track(
            make_body(), HTTP_AUTHORIZATION="Bearer invalid.token.value"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(Visitor.objects.get().user)

    def test_track_events_before_login_belong_to_user_after_login(self):
        visitor_id = str(uuid.uuid4())
        self.track(make_body(visitor_id=visitor_id))

        self.client.force_authenticate(user=self.user)
        self.track(make_body(visitor_id=visitor_id))

        visitor = Visitor.objects.get(id=visitor_id)
        self.assertEqual(visitor.user, self.user)
        self.assertEqual(
            Event.objects.filter(session__visitor=visitor).count(), 2
        )


class TrackEventsValidationTests(BaseApiTestCase):
    def test_track_invalid_data_saves_nothing(self):
        cases = {
            "unknown event name": make_body([make_event(event_name="hack")]),
            "event_id is not a uuid": make_body([make_event(event_id="1")]),
            "visitor_id is not a uuid": make_body(visitor_id="1"),
            "unknown device type": make_body(device_type="tv"),
            "empty events": make_body([]),
            "wrong timestamp": make_body(
                [make_event(event_timestamp="yesterday")]
            ),
            "too many events": make_body([make_event() for _ in range(51)]),
            "properties too large": make_body(
                [make_event(properties={"text": "x" * 3000})]
            ),
        }
        for name, body in cases.items():
            with self.subTest(name):
                res = self.track(body)
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(Event.objects.count(), 0)

    def test_track_session_is_required(self):
        body = make_body()
        del body["session"]

        res = self.track(body)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session", res.data)

    def test_track_max_events_accepted(self):
        res = self.track(make_body([make_event() for _ in range(50)]))

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.count(), 50)

    def test_track_optional_fields_can_be_null(self):
        event = make_event(page_path=None, movie_id=None, properties=None)

        res = self.track(make_body([event], device_type=None))

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)


class TrackEventsThrottleTests(BaseApiTestCase):
    def test_track_is_throttled(self):
        with mock.patch(
            "analytics.throttles.AnalyticsRateThrottle.get_rate",
            return_value="3/min",
        ):
            codes = [self.track(make_body()).status_code for _ in range(4)]

        self.assertEqual(codes[:3], [status.HTTP_201_CREATED] * 3)
        self.assertEqual(codes[3], status.HTTP_429_TOO_MANY_REQUESTS)
