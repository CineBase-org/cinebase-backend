from unittest import mock

from django.test import TestCase, override_settings
from rest_framework import status

PRIVATE_IP_HOST = "10.0.1.25:32768"


@override_settings(ALLOWED_HOSTS=["api.example.com"])
class HealthCheckHostTests(TestCase):
    def test_health_ok_with_private_ip_host(self):
        res = self.client.get("/health/", HTTP_HOST=PRIVATE_IP_HOST)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json(), {"status": "OK"})

    def test_health_ok_with_allowed_host(self):
        res = self.client.get("/health/", HTTP_HOST="api.example.com")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json(), {"status": "OK"})

    def test_other_paths_still_reject_unknown_host(self):
        res = self.client.get("/api/genres/", HTTP_HOST=PRIVATE_IP_HOST)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_paths_work_with_allowed_host(self):
        res = self.client.get("/api/genres/", HTTP_HOST="api.example.com")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_health_rejects_post(self):
        res = self.client.post("/health/", HTTP_HOST=PRIVATE_IP_HOST)
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


@override_settings(ALLOWED_HOSTS=["api.example.com"])
class HealthCheckDatabaseTests(TestCase):
    """The load balancer takes the server out when the database is down"""

    def test_health_503_when_database_is_down(self):
        with mock.patch(
            "cinema_base.healthy.connection.cursor",
            side_effect=Exception("database is down"),
        ):
            res = self.client.get("/health/", HTTP_HOST=PRIVATE_IP_HOST)

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("error", res.json())

    def test_health_503_when_the_query_fails(self):
        with mock.patch(
            "cinema_base.healthy.connection.cursor"
        ) as cursor:
            cursor.return_value.__enter__.return_value.execute.side_effect = (
                Exception("query failed")
            )
            res = self.client.get("/health/", HTTP_HOST="api.example.com")

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_health_ok_again_after_database_comes_back(self):
        with mock.patch(
            "cinema_base.healthy.connection.cursor",
            side_effect=Exception("database is down"),
        ):
            self.client.get("/health/", HTTP_HOST=PRIVATE_IP_HOST)

        res = self.client.get("/health/", HTTP_HOST=PRIVATE_IP_HOST)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
