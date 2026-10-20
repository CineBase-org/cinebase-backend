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
