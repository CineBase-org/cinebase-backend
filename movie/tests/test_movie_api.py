from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from django.test import TestCase

from movie.models import Movie, Rating, Watchlist, Genre


class MovieApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@example.com", password="pass12345"
        )
        self.movie = Movie.objects.create(tmdb_id=1, title="Test Movie")
        self.genre = Genre.objects.create(tmdb_id=1, name="Fantasy")

    def test_list_success(self):
        get_movie_list_res = self.client.get("/api/movies/")
        self.assertEqual(get_movie_list_res.status_code, status.HTTP_200_OK)

    def test_list_filter_by_genre(self):
        self.movie.genres.add(self.genre)

        other_genre = Genre.objects.create(tmdb_id=2, name="Some Genre")
        movie_without_genre = Movie.objects.create(
            tmdb_id=2, title="Another Movie"
        )
        movie_without_genre.genres.add(other_genre)

        res = self.client.get(f"/api/movies/?genres={self.genre.id}")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["title"], self.movie.title)
