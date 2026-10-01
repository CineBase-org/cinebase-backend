from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from django.test import TestCase

from movie.models import Movie, Rating, Watchlist, Genre


class RatingConstraintTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="test@example.com", password="pass12345"
        )
        self.movie = Movie.objects.create(tmdb_id=1, title="Test Movie")

    def test_score_out_of_range_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rating.objects.create(
                    user=self.user, movie=self.movie, score=10
                )


class WatchlistConstraintTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="test@example.com", password="pass12345"
        )
        self.movie = Movie.objects.create(tmdb_id=1, title="Test Movie")

    def test_duplicate_watchlist_entry_raises_integrity_error(self):
        Watchlist.objects.create(movie=self.movie, user=self.user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Watchlist.objects.create(movie=self.movie, user=self.user)


class MovieApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@example.com", password="pass12345"
        )
        self.movie = Movie.objects.create(tmdb_id=1, title="Test Movie")
        self.genre = Genre.objects.create(tmdb_id=1, name="Fantasy")

    def test_list_success(self):
        get_movie_list_res = self.client.get("/api/movie/movies/")
        self.assertEqual(get_movie_list_res.status_code, status.HTTP_200_OK)

    def test_list_filter_by_genre(self):
        self.movie.genres.add(self.genre)

        other_genre = Genre.objects.create(tmdb_id=2, name="Some Genre")
        movie_without_genre = Movie.objects.create(
            tmdb_id=2, title="Another Movie"
        )
        movie_without_genre.genres.add(other_genre)

        res = self.client.get(f"/api/movie/movies/?genres={self.genre.id}")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["title"], self.movie.title)
