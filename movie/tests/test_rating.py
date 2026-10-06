from rest_framework import status

from movie.models import Rating
from movie.tests.helpers import BaseApiTestCase, create_user


class RatingBaseTestCase(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = f"/api/movies/{self.movie.id}/rating/"
        self.other_user = create_user(
            email="other@example.com", password="Testtest!1"
        )
        Rating.objects.create(user=self.other_user, movie=self.movie, score=2)
        self.client.force_authenticate(user=self.user)


class RatingAccessTests(RatingBaseTestCase):
    def test_rating_requires_authentication(self):
        self.client.force_authenticate(user=None)
        res_get = self.client.get(self.url)
        self.assertEqual(res_get.status_code, status.HTTP_401_UNAUTHORIZED)

        res_put = self.client.put(self.url, {"score": 4}, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_401_UNAUTHORIZED)

        res_delete = self.client.delete(self.url)
        self.assertEqual(res_delete.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rating_movie_not_found(self):
        missing_url = "/api/movies/9999/rating/"

        res_get = self.client.get(missing_url)
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        res_put = self.client.put(missing_url, {"score": 4}, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_404_NOT_FOUND)

        res_delete = self.client.delete(missing_url)
        self.assertEqual(res_delete.status_code, status.HTTP_404_NOT_FOUND)


class RatingPutTests(RatingBaseTestCase):
    def test_create_rating(self):
        res_put = self.client.put(self.url, {"score": 4}, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_put.data["score"], 4)
        self.assertEqual(
            Rating.objects.filter(movie=self.movie, user=self.user).count(), 1
        )
        self.assertEqual(
            Rating.objects.get(movie=self.movie, user=self.user).score, 4
        )
        self.assertEqual(self.movie.ratings.count(), 2)
        self.assertEqual(
            Rating.objects.get(movie=self.movie, user=self.other_user).score, 2
        )

    def test_update_rating(self):
        res_put = self.client.put(self.url, {"score": 3}, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_201_CREATED)

        res_put_2 = self.client.put(self.url, {"score": 5}, format="json")
        self.assertEqual(res_put_2.status_code, status.HTTP_200_OK)

        self.assertEqual(
            Rating.objects.filter(movie=self.movie, user=self.user).count(), 1
        )
        self.assertEqual(
            Rating.objects.get(movie=self.movie, user=self.user).score, 5
        )
        self.assertEqual(Rating.objects.filter(movie=self.movie).count(), 2)
        self.assertEqual(
            Rating.objects.get(movie=self.movie, user=self.other_user).score, 2
        )

    def test_rating_score_out_of_range(self):
        res_put = self.client.put(self.url, {"score": 0}, format="json")
        res_put_2 = self.client.put(self.url, {"score": 6}, format="json")
        self.assertEqual(res_put.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res_put_2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Rating.objects.filter(movie=self.movie, user=self.user).count(), 0
        )
        self.assertEqual(
            Rating.objects.filter(
                movie=self.movie, user=self.other_user
            ).count(),
            1,
        )
        self.assertEqual(
            Rating.objects.get(movie=self.movie, user=self.other_user).score, 2
        )
        self.assertIn("score", res_put.data)


class RatingDeleteTests(RatingBaseTestCase):
    def test_delete_rating(self):
        Rating.objects.create(user=self.user, movie=self.movie, score=4)
        res_delete = self.client.delete(self.url)
        self.assertEqual(res_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Rating.objects.filter(movie=self.movie).count(), 1)
        self.assertEqual(
            Rating.objects.filter(movie=self.movie, user=self.user).count(), 0
        )
        self.assertEqual(
            Rating.objects.filter(
                movie=self.movie, user=self.other_user
            ).count(),
            1,
        )

    def test_delete_missing_rating(self):
        res_delete = self.client.delete(self.url)
        self.assertEqual(res_delete.status_code, status.HTTP_404_NOT_FOUND)


class RatingGetTests(RatingBaseTestCase):
    def test_get_rating_returns_null_if_not_rated(self):
        res_get = self.client.get(self.url)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["score"], None)

    def test_get_existing_rating(self):
        Rating.objects.create(user=self.user, movie=self.movie, score=4)
        res_get = self.client.get(self.url)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["score"], 4)
