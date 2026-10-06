from rest_framework import status

from movie.models import Movie, Genre, Rating
from movie.tests.helpers import BaseApiTestCase, create_user, create_movie


class MovieListTests(BaseApiTestCase):
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


class MovieDetailTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = f"/api/movies/{self.movie.id}/"

    def test_retrieve_movie(self):
        self.client.force_authenticate(user=None)
        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["title"], self.movie.title)
        self.assertEqual(get_res.data["id"], self.movie.id)

    def test_retrieve_movie_ratings_summary(self):
        other_user = create_user(email="test@test.com", password="testtest")
        Rating.objects.create(user=self.user, movie=self.movie, score=2)
        Rating.objects.create(user=other_user, movie=self.movie, score=4)
        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["average_rating"], 3.0)
        self.assertEqual(get_res.data["ratings_count"], 2)

    def test_retrieve_movie_without_ratings(self):
        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["average_rating"], None)
        self.assertEqual(get_res.data["ratings_count"], 0)

    def test_retrieve_movie_trailer_url(self):
        movie_with_trailer = create_movie(
            tmdb_id=5, title="Trailer", trailer_youtube_id="abc123"
        )
        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["trailer_url"], None)

        get_res_2 = self.client.get(f"/api/movies/{movie_with_trailer.id}/")
        self.assertEqual(get_res_2.status_code, status.HTTP_200_OK)
        self.assertEqual(
            get_res_2.data["trailer_url"],
            f"https://www.youtube.com/watch?v={movie_with_trailer.trailer_youtube_id}",
        )

    def test_retrieve_missing_movie(self):
        get_res = self.client.get("/api/movies/99999/")
        self.assertEqual(get_res.status_code, status.HTTP_404_NOT_FOUND)
