from rest_framework import status

from movie.models import Comment
from movie.tests.helpers import (
    BaseApiTestCase,
    create_user,
    create_comment,
    create_movie,
)


class CommentBaseTestCase(BaseApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = "/api/comments/"
        self.other_user = create_user(
            email="other@example.com", password="Testtest!1"
        )
        self.client.force_authenticate(user=self.user)


class CommentCreateTests(CommentBaseTestCase):
    def test_create_comment_required_authentication(self):
        self.client.force_authenticate(user=None)
        post_res = self.client.post(
            self.url,
            {"movie": self.movie.id, "text": "test comment"},
            format="json",
        )
        self.assertEqual(post_res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Comment.objects.count(), 0)

    def test_create_comment(self):
        post_res = self.client.post(
            self.url,
            {"movie": self.movie.id, "text": "test comment"},
        )
        self.assertEqual(post_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(Comment.objects.filter(user=self.user).count(), 1)
        self.assertEqual(post_res.data["text"], "test comment")
        self.assertEqual(post_res.data["parent"], None)
        self.assertEqual(post_res.data["likes_count"], 0)
        self.assertEqual(post_res.data["is_liked"], False)

    def test_create_comment_invalid_data(self):
        post_res_invalid_text = self.client.post(
            self.url,
            {"movie": self.movie.id},
        )
        self.assertEqual(
            post_res_invalid_text.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(Comment.objects.count(), 0)

        post_res_invalid_movie = self.client.post(
            self.url,
            {"movie": "99999", "text": "test comment"},
        )
        self.assertEqual(
            post_res_invalid_movie.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(Comment.objects.count(), 0)

        post_res_not_movie = self.client.post(
            self.url,
            {"text": "test comment"},
        )
        self.assertEqual(
            post_res_not_movie.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(Comment.objects.count(), 0)

    def test_create_reply(self):
        parent = create_comment(self.other_user, self.movie)

        res_post = self.client.post(
            self.url,
            {
                "movie": self.movie.id,
                "text": "test comment",
                "parent": parent.id,
            },
        )
        self.assertEqual(res_post.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_post.data["parent"], parent.id)
        self.assertEqual(Comment.objects.count(), 2)
        self.assertEqual(
            Comment.objects.filter(parent=parent, user=self.user).count(), 1
        )

    def test_reply_to_reply_rejected(self):
        parent = create_comment(self.other_user, self.movie)
        reply = create_comment(self.other_user, self.movie, parent=parent)

        res_post = self.client.post(
            self.url,
            {
                "movie": self.movie.id,
                "text": "test comment",
                "parent": reply.id,
            },
        )
        self.assertEqual(res_post.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Comment.objects.count(), 2)

    def test_reply_to_other_movie_comment_rejected(self):
        movie_2 = create_movie(tmdb_id=2, title="Movie")
        parent = create_comment(self.other_user, self.movie)

        res_post = self.client.post(
            self.url,
            {
                "movie": movie_2.id,
                "text": "test comment",
                "parent": parent.id,
            },
        )
        self.assertEqual(res_post.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Comment.objects.count(), 1)
