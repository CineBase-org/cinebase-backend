from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from analytics.models import Event, Session, Visitor
from movie.models import Movie


class AnalyticsAdminTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser(
            email="admin@example.com", password="pass12345"
        )
        self.client.force_login(admin)

        now = timezone.now()
        movie = Movie.objects.create(tmdb_id=1, title="Test Movie")
        self.visitor = Visitor.objects.create()
        self.session = Session.objects.create(
            visitor=self.visitor, started_at=now, device_type="desktop"
        )
        self.event = Event.objects.create(
            session=self.session,
            event_name="page_view",
            event_timestamp=now,
            page_path="/movies",
            movie=movie,
        )

    def test_models_are_in_the_admin(self):
        for name in ("visitor", "session", "event"):
            with self.subTest(model=name):
                url = reverse(f"admin:analytics_{name}_changelist")

                res = self.client.get(url)

                self.assertEqual(res.status_code, 200)

    def test_list_filters_work(self):
        url = reverse("admin:analytics_event_changelist")

        res = self.client.get(url, {"event_name": "page_view"})

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "/movies")

    def test_objects_can_be_viewed(self):
        for name, obj in (
            ("visitor", self.visitor),
            ("session", self.session),
            ("event", self.event),
        ):
            with self.subTest(model=name):
                res = self.client.get(
                    reverse(f"admin:analytics_{name}_change", args=[obj.pk])
                )

                self.assertEqual(res.status_code, 200)

    def test_data_cannot_be_added(self):
        for name in ("visitor", "session", "event"):
            with self.subTest(model=name):
                res = self.client.get(reverse(f"admin:analytics_{name}_add"))

                self.assertEqual(res.status_code, 403)

    def test_data_cannot_be_changed(self):
        res = self.client.post(
            reverse("admin:analytics_event_change", args=[self.event.pk]),
            {"event_name": "page_view", "page_path": "/hacked"},
        )

        self.assertEqual(res.status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.page_path, "/movies")
