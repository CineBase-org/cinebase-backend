from rest_framework import status

from movie.models import CommentLike
from movie.tests.helpers import BaseApiTestCase, create_user, create_comment


class LikeBaseTestCase(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.other_user = create_user(
            email="other@example.com", password="Testtest!1"
        )
        self.comment = create_comment(self.other_user, self.movie)
        self.url = f"/api/comments/{self.comment.id}/likes/"
        self.client.force_authenticate(user=self.user)


class LikeAccessTests(LikeBaseTestCase):
    def test_likes_require_authentication(self):
        self.client.force_authenticate(user=None)
        put_res = self.client.put(self.url)
        self.assertEqual(put_res.status_code, status.HTTP_401_UNAUTHORIZED)

        delete_res = self.client.delete(self.url)
        self.assertEqual(delete_res.status_code, status.HTTP_401_UNAUTHORIZED)

        self.assertEqual(CommentLike.objects.count(), 0)

    def test_like_not_found(self):
        missing_url = "/api/comments/99999/likes/"
        put_res = self.client.put(missing_url)
        self.assertEqual(put_res.status_code, status.HTTP_404_NOT_FOUND)

        delete_res = self.client.delete(missing_url)
        self.assertEqual(delete_res.status_code, status.HTTP_404_NOT_FOUND)


class LikePutTests(LikeBaseTestCase):
    def test_like_comment(self):
        put_res = self.client.put(self.url)
        self.assertEqual(put_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(put_res.data["liked"], True)
        self.assertEqual(CommentLike.objects.filter(user=self.user).count(), 1)

    def test_like_twice(self):
        put_res = self.client.put(self.url)
        self.assertEqual(put_res.status_code, status.HTTP_201_CREATED)

        put_res_2 = self.client.put(self.url)
        self.assertEqual(put_res_2.status_code, status.HTTP_200_OK)
        self.assertEqual(CommentLike.objects.filter(user=self.user).count(), 1)


class LikeDeleteTests(LikeBaseTestCase):
    def test_remove_like(self):
        CommentLike.objects.create(user=self.user, comment=self.comment)
        CommentLike.objects.create(user=self.other_user, comment=self.comment)

        del_res = self.client.delete(self.url)
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.assertEqual(del_res.data["liked"], False)
        self.assertEqual(
            CommentLike.objects.filter(user=self.other_user).count(), 1
        )
        self.assertEqual(CommentLike.objects.filter(user=self.user).count(), 0)

    def test_remove_missing_like(self):
        del_res = self.client.delete(self.url)
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.assertEqual(del_res.data["liked"], False)
