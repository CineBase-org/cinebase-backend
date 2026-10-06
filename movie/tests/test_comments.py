from rest_framework import status

from movie.models import Comment, CommentLike
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


class CommentListTests(CommentBaseTestCase):
    def test_list_without_authentication(self):
        comment = create_comment(self.user, self.movie)
        create_comment(self.other_user, self.movie)
        CommentLike.objects.create(user=self.other_user, comment=comment)

        self.client.force_authenticate(user=None)

        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(get_res.data["results"]), 2)
        for com in get_res.data["results"]:
            self.assertEqual(com["is_liked"], False)

        liked = next(
            c for c in get_res.data["results"] if c["id"] == comment.id
        )
        self.assertEqual(liked["likes_count"], 1)

    def test_list_filter_by_movie(self):
        movie = create_movie(tmdb_id=2, title="Movie")
        create_comment(self.user, self.movie)
        comment = create_comment(self.other_user, movie)

        get_res = self.client.get(self.url + "?movie=" + str(movie.id))
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(get_res.data["results"]), 1)
        self.assertEqual(get_res.data["results"][0]["id"], comment.id)

    def test_list_newest_first(self):
        first = create_comment(self.user, self.movie)
        second = create_comment(self.user, self.movie)
        third = create_comment(self.user, self.movie)

        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        ids = [c["id"] for c in get_res.data["results"]]
        self.assertEqual(ids, [third.id, second.id, first.id])

    def test_list_is_liked_and_likes_count_for_authenticated_user(self):
        comment_with_likes = create_comment(self.user, self.movie)
        comment_without_likes = create_comment(self.user, self.movie)
        CommentLike.objects.create(user=self.user, comment=comment_with_likes)
        CommentLike.objects.create(
            user=self.other_user, comment=comment_with_likes
        )

        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        results = get_res.data["results"]
        liked = next(c for c in results if c["id"] == comment_with_likes.id)
        plain = next(c for c in results if c["id"] == comment_without_likes.id)
        self.assertEqual(liked["is_liked"], True)
        self.assertEqual(liked["likes_count"], 2)
        self.assertEqual(plain["is_liked"], False)
        self.assertEqual(plain["likes_count"], 0)

    def test_list_invalid_movie_param(self):
        get_res = self.client.get(self.url + "?movie=abd")
        self.assertEqual(get_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("movie", get_res.data)

        get_res_2 = self.client.get(self.url + "?movie=1.6")
        self.assertEqual(get_res_2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("movie", get_res_2.data)

    def test_comment_author_name(self):
        user1 = create_user(
            email="t@test.com",
            password="testtest",
            first_name="Test",
            last_name="Test",
        )
        user2 = create_user(
            email="te@test.com",
            password="testtest",
            first_name="Test1",
        )
        user3 = create_user(email="test@test.com", password="testtest")

        comment1 = create_comment(user1, self.movie)
        comment2 = create_comment(user2, self.movie)
        comment3 = create_comment(user3, self.movie)

        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        results = get_res.data["results"]
        first_last_name = next(c for c in results if c["id"] == comment1.id)
        first_name = next(c for c in results if c["id"] == comment2.id)
        no_name = next(c for c in results if c["id"] == comment3.id)

        self.assertEqual(first_last_name["author"], "Test Test")
        self.assertEqual(first_name["author"], "Test1")
        self.assertEqual(no_name["author"], "User" + str(user3.id))


class CommentRetrieveTests(CommentBaseTestCase):
    def test_retrieve_comment(self):
        comment = create_comment(self.user, self.movie)
        get_res = self.client.get(self.url + str(comment.id) + "/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["text"], comment.text)

    def test_retrieve_comment_not_found(self):
        get_res = self.client.get(self.url + "99999/")
        self.assertEqual(get_res.status_code, status.HTTP_404_NOT_FOUND)


class CommentDeleteTests(CommentBaseTestCase):
    def test_delete_requires_authentication(self):
        comment = create_comment(self.user, self.movie)
        self.client.force_authenticate(user=None)
        delete_res = self.client.delete(self.url + str(comment.id) + "/")
        self.assertEqual(delete_res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Comment.objects.filter(id=comment.id).exists())

    def test_author_can_delete(self):
        comment = create_comment(self.user, self.movie)

        delete_res = self.client.delete(self.url + str(comment.id) + "/")
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Comment.objects.filter(id=comment.id).exists())

    def test_other_user_cannot_delete(self):
        comment = create_comment(self.other_user, self.movie)
        delete_res = self.client.delete(self.url + str(comment.id) + "/")
        self.assertEqual(delete_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Comment.objects.filter(id=comment.id).exists())

    def test_admin_can_delete_any(self):
        admin = create_user(
            email="admin@admin.com", password="adminadmin", is_staff=True
        )
        self.client.force_authenticate(user=admin)
        comment = create_comment(self.user, self.movie)

        delete_res_1 = self.client.delete(self.url + str(comment.id) + "/")
        self.assertEqual(delete_res_1.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Comment.objects.filter(movie=self.movie).count(), 0)

    def test_delete_missing_comment(self):
        create_comment(self.user, self.movie)
        delete_res_1 = self.client.delete(self.url + "99999/")
        self.assertEqual(delete_res_1.status_code, status.HTTP_404_NOT_FOUND)
