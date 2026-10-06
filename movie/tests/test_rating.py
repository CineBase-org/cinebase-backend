from rest_framework import status

from movie.tests.helpers import BaseApiTestCase


class RatingBaseTestCase(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = f"/api/movies/{self.movie.id}/rating/"


class RatingAccessTests(RatingBaseTestCase):
    def test_rating_requires_authentication(self):
        res_get = self.client.get(self.url)
        self.assertEqual(res_get.status_code, status.HTTP_401_UNAUTHORIZED)

        res_put = self.client.put(self.url, {"score": 4}, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_401_UNAUTHORIZED)

        res_delete = self.client.delete(self.url)
        self.assertEqual(res_delete.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rating_movie_not_found(self):
        self.client.force_authenticate(user=self.user)
        missing_url = "/api/movies/9999/rating/"

        res_get = self.client.get(missing_url)
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        res_put = self.client.put(missing_url, {"score": 4}, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_404_NOT_FOUND)

        res_delete = self.client.delete(missing_url)
        self.assertEqual(res_delete.status_code, status.HTTP_404_NOT_FOUND)
