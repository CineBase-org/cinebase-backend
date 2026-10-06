from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


def create_user(email="test@example.com", password="pass12345", **params):
    return get_user_model().objects.create_user(
        email=email, password=password, **params
    )


class BaseApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
