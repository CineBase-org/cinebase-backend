import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient


class BaseApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = create_user()
        self.url = "/api/analytics/events/"

    def track(self, body, **extra):
        return self.client.post(self.url, body, format="json", **extra)


def create_user(email="test@example.com", password="pass12345", **params):
    return get_user_model().objects.create_user(
        email=email, password=password, **params
    )


def make_event(**params):
    event = {
        "event_id": str(uuid.uuid4()),
        "event_name": "movie_card_click",
        "event_timestamp": "2026-11-10T10:00:00Z",
    }
    event.update(params)
    return event


def make_body(events=None, visitor_id=None, session_id=None, **session):
    session_data = {
        "session_id": session_id or str(uuid.uuid4()),
        "started_at": "2026-11-10T09:59:00Z",
        "device_type": "mobile",
    }
    session_data.update(session)
    return {
        "visitor_id": visitor_id or str(uuid.uuid4()),
        "session": session_data,
        "events": [make_event()] if events is None else events,
    }
