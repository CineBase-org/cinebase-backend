from rest_framework import status


from movie.models import Movie, Genre
from movie.tests.helpers import BaseApiTestCase


class MovieApiTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.genre = Genre.objects.create(tmdb_id=1, name="Fantasy")
        self.other_genre = Genre.objects.create(tmdb_id=2, name="Some Genre")
        self.url = "/api/movies/"

    def test_list_success(self):
        get_movie_list_res = self.client.get(self.url)
        self.assertEqual(get_movie_list_res.status_code, status.HTTP_200_OK)

    def test_list_filter_by_genre(self):
        self.movie.genres.add(self.genre)
        movie_other_genre = Movie.objects.create(
            tmdb_id=2, title="Another Movie"
        )
        movie_other_genre.genres.add(self.other_genre)

        res = self.client.get(self.url + f"?genres={self.genre.id}")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["title"], self.movie.title)

    def test_list_filter_by_multiple_genres(self):
        self.movie.genres.add(self.other_genre)
        movie2 = Movie.objects.create(tmdb_id=2, title="Test Movie")
        movie2.genres.add(self.genre)
        Movie.objects.create(tmdb_id=3, title="Movie")
        get_res = self.client.get(
            self.url + f"?genres={self.genre.id},{self.other_genre.id}"
        )

        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

        self.assertEqual(len(get_res.data["results"]), 2)

    def test_list_invalid_genres_param(self):
        get_res = self.client.get(self.url + "?genres=invalid")
        self.assertEqual(get_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("genres", get_res.data)

    def test_list_search_by_title_start(self):
        Movie.objects.create(tmdb_id=6, title="Movie")
        Movie.objects.create(tmdb_id=7, title="Test")
        res = self.client.get(self.url + "?search=mo")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["title"], "Movie")

    def test_list_search_and_genre_combined(self):
        self.movie.genres.add(self.other_genre)
        movie2 = Movie.objects.create(tmdb_id=3, title="Dune")
        movie2.genres.add(self.genre)
        movie3 = Movie.objects.create(tmdb_id=6, title="Movie")
        movie3.genres.add(self.genre)
        movie4 = Movie.objects.create(tmdb_id=8, title="Dune Part Two")
        movie4.genres.add(self.other_genre)
        Movie.objects.create(tmdb_id=7, title="Test")

        get_res = self.client.get(
            self.url + f"?genres={self.genre.id}&search=du"
        )
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(get_res.data["results"]), 1)
        self.assertEqual(get_res.data["results"][0]["title"], "Dune")
