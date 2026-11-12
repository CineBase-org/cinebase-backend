from rest_framework import status

from movie.models import Genre, Watchlist
from movie.tests.helpers import BaseApiTestCase, create_movie, create_user


class WatchlistBaseTestCase(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = f"/api/movies/{self.movie.id}/watchlist/"
        self.client.force_authenticate(user=self.user)
        self.other_user = create_user(
            email="other@example.com", password="Testtest1!"
        )
        Watchlist.objects.create(user=self.other_user, movie=self.movie)


class WatchlistAccessTests(WatchlistBaseTestCase):
    def test_watchlist_requires_authentication(self):
        self.client.force_authenticate(user=None)
        res_get = self.client.get(self.url)
        self.assertEqual(res_get.status_code, status.HTTP_401_UNAUTHORIZED)

        res_put = self.client.put(self.url)
        self.assertEqual(res_put.status_code, status.HTTP_401_UNAUTHORIZED)

        res_delete = self.client.delete(self.url)
        self.assertEqual(res_delete.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_watchlist_movie_not_found(self):
        missing_url = "/api/movies/9999/watchlist/"
        res_get = self.client.get(missing_url)
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        res_put = self.client.put(missing_url)
        self.assertEqual(res_put.status_code, status.HTTP_404_NOT_FOUND)

        res_delete = self.client.delete(missing_url)
        self.assertEqual(res_delete.status_code, status.HTTP_404_NOT_FOUND)


class WatchlistGetTests(WatchlistBaseTestCase):
    def test_get_returns_false_if_not_in_watchlist(self):
        res_get = self.client.get(self.url)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["in_watchlist"], False)

    def test_get_returns_true_if_watchlist(self):
        Watchlist.objects.create(user=self.user, movie=self.movie)
        res_get = self.client.get(self.url)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["in_watchlist"], True)


class WatchlistPutTests(WatchlistBaseTestCase):
    def test_add_to_watchlist(self):
        res_put = self.client.put(self.url)
        self.assertEqual(res_put.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_put.data["in_watchlist"], True)
        self.assertEqual(Watchlist.objects.filter(user=self.user).count(), 1)

    def test_add_to_watchlist_twice(self):
        res_put = self.client.put(self.url)
        self.assertEqual(res_put.status_code, status.HTTP_201_CREATED)
        res_put_2 = self.client.put(self.url)
        self.assertEqual(res_put_2.status_code, status.HTTP_200_OK)
        self.assertEqual(Watchlist.objects.filter(user=self.user).count(), 1)

    def test_add_does_not_affect_other_users(self):
        res_put = self.client.put(self.url)
        self.assertEqual(res_put.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Watchlist.objects.filter(movie=self.movie).count(), 2)
        self.assertEqual(
            Watchlist.objects.filter(user=self.other_user).count(), 1
        )


class WatchlistDeleteTests(WatchlistBaseTestCase):
    def test_remove_from_watchlist(self):
        Watchlist.objects.create(user=self.user, movie=self.movie)
        res_delete = self.client.delete(self.url)
        self.assertEqual(res_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Watchlist.objects.filter(user=self.user).count(), 0)
        self.assertEqual(
            Watchlist.objects.filter(user=self.other_user).count(), 1
        )

    def test_remove_missing_from_watchlist(self):
        res_delete = self.client.delete(self.url)
        self.assertEqual(res_delete.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Watchlist.objects.filter(user=self.user).count(), 0)
        self.assertEqual(Watchlist.objects.filter(movie=self.movie).count(), 1)
        self.assertEqual(
            Watchlist.objects.filter(user=self.other_user).count(), 1
        )


class WatchlistListTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = "/api/watchlist/"
        self.client.force_authenticate(user=self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_watchlist_returns_empty_array(self):
        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    def test_returns_movies_with_list_fields(self):
        Watchlist.objects.create(user=self.user, movie=self.movie)

        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["id"], self.movie.id)
        for key in ("title", "genres", "poster_path", "trailer_url"):
            self.assertIn(key, res.data[0])

    def test_returns_only_own_movies(self):
        stranger = create_user(email="stranger@example.com")
        other_movie = create_movie(tmdb_id=2, title="Not mine")
        Watchlist.objects.create(user=self.user, movie=self.movie)
        Watchlist.objects.create(user=stranger, movie=other_movie)
        Watchlist.objects.create(user=stranger, movie=self.movie)

        res = self.client.get(self.url)

        self.assertEqual([m["id"] for m in res.data], [self.movie.id])

    def test_most_recently_added_first(self):
        second = create_movie(tmdb_id=2, title="Second")
        third = create_movie(tmdb_id=3, title="Third")
        stranger = create_user(email="stranger@example.com")
        # Entries of another user must not break the order
        Watchlist.objects.create(user=stranger, movie=third)
        Watchlist.objects.create(user=self.user, movie=self.movie)
        Watchlist.objects.create(user=self.user, movie=third)
        Watchlist.objects.create(user=self.user, movie=second)

        res = self.client.get(self.url)

        self.assertEqual(
            [m["id"] for m in res.data], [second.id, third.id, self.movie.id]
        )

    def test_returns_all_movies_without_pagination(self):
        for number in range(2, 22):
            movie = create_movie(tmdb_id=number, title=f"Movie {number}")
            Watchlist.objects.create(user=self.user, movie=movie)

        res = self.client.get(self.url)

        self.assertIsInstance(res.data, list)
        self.assertEqual(len(res.data), 20)

    def test_removed_movie_disappears(self):
        Watchlist.objects.create(user=self.user, movie=self.movie)
        self.client.delete(f"/api/movies/{self.movie.id}/watchlist/")

        res = self.client.get(self.url)

        self.assertEqual(res.data, [])

    def test_genres_do_not_cause_extra_queries(self):
        genre_a = Genre.objects.create(tmdb_id=1, name="A")
        genre_b = Genre.objects.create(tmdb_id=2, name="B")
        for number in range(2, 8):
            movie = create_movie(tmdb_id=number, title=f"Movie {number}")
            movie.genres.add(genre_a, genre_b)
            Watchlist.objects.create(user=self.user, movie=movie)

        with self.assertNumQueries(2):
            res = self.client.get(self.url)

        self.assertEqual(len(res.data), 6)
