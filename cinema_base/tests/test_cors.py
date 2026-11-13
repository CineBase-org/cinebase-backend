from django.test import TestCase, override_settings

FRONTEND = "https://cinebase.fun"
EVENTS_URL = "/api/analytics/events/"


@override_settings(
    CORS_ALLOW_ALL_ORIGINS=False, CORS_ALLOWED_ORIGINS=[FRONTEND]
)
class CorsTests(TestCase):
    def preflight(self, origin=FRONTEND, headers="content-type"):
        return self.client.options(
            EVENTS_URL,
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=headers,
        )

    def test_preflight_from_frontend_allows_credentials(self):
        res = self.preflight()

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Access-Control-Allow-Origin"], FRONTEND)
        self.assertEqual(res["Access-Control-Allow-Credentials"], "true")

    def test_preflight_allows_headers_the_frontend_sends(self):
        res = self.preflight(
            headers="content-type,authorization,x-csrftoken"
        )

        allowed = res["Access-Control-Allow-Headers"].lower()
        for header in ("content-type", "authorization", "x-csrftoken"):
            self.assertIn(header, allowed)

    def test_post_from_frontend_gets_cors_headers(self):
        res = self.client.post(
            EVENTS_URL,
            {},
            content_type="application/json",
            HTTP_ORIGIN=FRONTEND,
        )

        self.assertEqual(res["Access-Control-Allow-Origin"], FRONTEND)
        self.assertEqual(res["Access-Control-Allow-Credentials"], "true")

    def test_other_origins_are_not_allowed(self):
        for origin in (
            "https://evil.example.com",
            "https://www.cinebase.fun",
            "http://cinebase.fun",
        ):
            with self.subTest(origin=origin):
                res = self.preflight(origin=origin)

                self.assertNotIn("Access-Control-Allow-Origin", res)
                self.assertNotIn("Access-Control-Allow-Credentials", res)

    def test_no_cors_headers_without_origin(self):
        res = self.client.post(
            EVENTS_URL, {}, content_type="application/json"
        )

        self.assertNotIn("Access-Control-Allow-Origin", res)
