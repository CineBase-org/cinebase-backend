from rest_framework import status

from movie.models import Watchlist
from movie.tests.helpers import BaseApiTestCase, create_user


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
