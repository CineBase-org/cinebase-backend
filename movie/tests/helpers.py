from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from movie.models import Movie


class BaseApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.movie = create_movie()


def create_user(email="test@example.com", password="pass12345", **params):
    return get_user_model().objects.create_user(
        email=email, password=password, **params
    )


def create_movie(tmdb_id=1, title="Test Movie", **params):
    return Movie.objects.create(tmdb_id=tmdb_id, title=title, **params)
