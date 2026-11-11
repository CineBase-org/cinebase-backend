from datetime import date

from rest_framework import status

from movie.models import Movie, Genre
from movie.tests.helpers import BaseApiTestCase, create_movie


class MovieRandomTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.genre = Genre.objects.create(tmdb_id=1, name="Fantasy")
        self.url = "/api/movies/random/"

    def test_random_returns_detail_movie(self):
        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], self.movie.id)
        for key in (
            "overview",
            "cast",
            "average_rating",
            "ratings_count",
            "streaming_platforms",
        ):
            self.assertIn(key, res.data)

    def test_random_no_movies(self):
        Movie.objects.all().delete()

        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", res.data)

    def test_random_returns_different_movies(self):
        create_movie(tmdb_id=2, title="Second Movie")

        seen = {self.client.get(self.url).data["id"] for _ in range(30)}

        self.assertEqual(len(seen), 2)

    def test_random_filter_by_genre(self):
        self.movie.genres.add(self.genre)
        create_movie(tmdb_id=2, title="No genre")

        for _ in range(10):
            res = self.client.get(self.url + f"?genres={self.genre.id}")
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data["id"], self.movie.id)

    def test_random_filter_by_multiple_genres_requires_all(self):
        other_genre = Genre.objects.create(tmdb_id=2, name="Drama")
        self.movie.genres.add(self.genre)
        both = create_movie(tmdb_id=2, title="Both genres")
        both.genres.add(self.genre, other_genre)

        for _ in range(10):
            res = self.client.get(
                self.url + f"?genres={self.genre.id},{other_genre.id}"
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data["id"], both.id)

    def test_random_filter_by_min_rating(self):
        good = create_movie(tmdb_id=2, title="Good", vote_average=8.5)

        for _ in range(10):
            res = self.client.get(self.url + "?min_rating=8")
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data["id"], good.id)

    def test_random_filter_by_years(self):
        inside = create_movie(
            tmdb_id=2, title="Inside", release_date=date(2012, 5, 1)
        )
        create_movie(tmdb_id=3, title="Too old", release_date=date(2000, 1, 1))
        create_movie(tmdb_id=4, title="Too new", release_date=date(2020, 1, 1))

        for _ in range(10):
            res = self.client.get(self.url + "?year_from=2010&year_to=2015")
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data["id"], inside.id)

    def test_random_filters_combined(self):
        match = create_movie(
            tmdb_id=2,
            title="Match",
            vote_average=8,
            release_date=date(2012, 5, 1),
        )
        match.genres.add(self.genre)
        create_movie(
            tmdb_id=3,
            title="Wrong genre",
            vote_average=8,
            release_date=date(2012, 5, 1),
        )
        low_rating = create_movie(
            tmdb_id=4,
            title="Low rating",
            vote_average=5,
            release_date=date(2012, 5, 1),
        )
        low_rating.genres.add(self.genre)
        wrong_year = create_movie(
            tmdb_id=5,
            title="Wrong year",
            vote_average=8,
            release_date=date(1999, 1, 1),
        )
        wrong_year.genres.add(self.genre)

        query = (
            f"?genres={self.genre.id}&min_rating=7"
            "&year_from=2000&year_to=2020"
        )
        for _ in range(10):
            res = self.client.get(self.url + query)
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data["id"], match.id)

    def test_random_nothing_matches(self):
        res = self.client.get(self.url + "?min_rating=9")

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_random_invalid_params(self):
        cases = [
            ("min_rating", "abc"),
            ("min_rating", "11"),
            ("min_rating", "-1"),
            ("year_from", "abc"),
            ("year_from", "0"),
            ("year_to", "10000"),
            ("genres", "abc"),
        ]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                res = self.client.get(self.url + f"?{name}={value}")
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(name, res.data)
