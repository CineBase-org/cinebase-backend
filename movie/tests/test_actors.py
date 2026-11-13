from rest_framework import status

from movie.models import Genre, MovieCast, Person
from movie.tests.helpers import BaseApiTestCase, create_movie


def add_actor(movie, person, character="Role", order=0):
    return MovieCast.objects.create(
        movie=movie, person=person, character=character, order=order
    )


def create_person(tmdb_id=100, name="Tom Holland", profile_path="/tom.jpg"):
    return Person.objects.create(
        tmdb_id=tmdb_id, name=name, profile_path=profile_path
    )


class ActorBaseTestCase(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.tom = create_person()
        self.zendaya = create_person(
            tmdb_id=200, name="Zendaya", profile_path="/zendaya.jpg"
        )
        # self.movie: Tom and Zendaya
        add_actor(self.movie, self.tom, "Peter", 0)
        add_actor(self.movie, self.zendaya, "MJ", 1)
        # second movie: only Tom
        self.second = create_movie(tmdb_id=2, title="Second")
        add_actor(self.second, self.tom, "Peter again", 0)
        # third movie: nobody from the two
        self.third = create_movie(tmdb_id=3, title="Third")
        add_actor(self.third, create_person(300, "Someone Else"), "X", 0)


class CastPersonIdTests(ActorBaseTestCase):
    def test_cast_has_person_id(self):
        res = self.client.get(f"/api/movies/{self.movie.id}/")

        by_name = {item["name"]: item for item in res.data["cast"]}
        self.assertEqual(by_name["Tom Holland"]["person_id"], self.tom.id)
        self.assertEqual(by_name["Zendaya"]["person_id"], self.zendaya.id)

    def test_person_id_is_the_same_in_every_movie(self):
        first = self.client.get(f"/api/movies/{self.movie.id}/")
        second = self.client.get(f"/api/movies/{self.second.id}/")

        first_tom = next(
            c for c in first.data["cast"] if c["name"] == "Tom Holland"
        )
        second_tom = second.data["cast"][0]
        self.assertEqual(first_tom["person_id"], second_tom["person_id"])
        # while the id of the cast entry differs
        self.assertNotEqual(first_tom["id"], second_tom["id"])

    def test_old_cast_fields_are_still_there(self):
        res = self.client.get(f"/api/movies/{self.movie.id}/")

        for key in ("id", "name", "profile_path", "character", "order"):
            self.assertIn(key, res.data["cast"][0])


class ActorFilterTests(ActorBaseTestCase):
    url = "/api/movies/"

    def ids(self, res):
        return sorted(movie["id"] for movie in res.data["results"])

    def test_returns_only_movies_of_the_actor(self):
        res = self.client.get(self.url, {"actor": self.tom.id})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.ids(res), sorted([self.movie.id, self.second.id])
        )

    def test_actor_in_one_movie(self):
        res = self.client.get(self.url, {"actor": self.zendaya.id})

        self.assertEqual(self.ids(res), [self.movie.id])

    def test_unknown_actor_gives_empty_list(self):
        res = self.client.get(self.url, {"actor": 999999})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 0)

    def test_without_filter_all_movies_are_returned(self):
        res = self.client.get(self.url)

        self.assertEqual(res.data["count"], 3)

    def test_no_duplicates_when_actor_has_two_roles_in_a_movie(self):
        add_actor(self.movie, self.tom, "Second role", 5)

        res = self.client.get(self.url, {"actor": self.tom.id})

        self.assertEqual(res.data["count"], 2)

    def test_combined_with_genres(self):
        action = Genre.objects.create(tmdb_id=1, name="Action")
        self.second.genres.add(action)

        res = self.client.get(
            self.url, {"actor": self.tom.id, "genres": action.id}
        )

        self.assertEqual(self.ids(res), [self.second.id])

    def test_combined_with_search(self):
        res = self.client.get(
            self.url, {"actor": self.tom.id, "search": "Sec"}
        )

        self.assertEqual(self.ids(res), [self.second.id])

    def test_result_is_paginated_with_the_same_format(self):
        res = self.client.get(self.url, {"actor": self.tom.id})

        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, res.data)
        self.assertIn("title", res.data["results"][0])

    def test_invalid_values(self):
        for value in ("abc", "0", "-1", "1.5", "99999999999", ""):
            with self.subTest(value=value):
                res = self.client.get(self.url, {"actor": value})

                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("actor", res.data)


class PersonDetailTests(ActorBaseTestCase):
    def test_returns_actor(self):
        res = self.client.get(f"/api/people/{self.tom.id}/")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data,
            {
                "id": self.tom.id,
                "name": "Tom Holland",
                "profile_path": "/tom.jpg",
                "movies_count": 2,
            },
        )

    def test_movies_count_for_one_movie(self):
        res = self.client.get(f"/api/people/{self.zendaya.id}/")

        self.assertEqual(res.data["movies_count"], 1)

    def test_actor_without_profile_path(self):
        person = create_person(tmdb_id=400, name="No Photo", profile_path=None)

        res = self.client.get(f"/api/people/{person.id}/")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["profile_path"])
        self.assertEqual(res.data["movies_count"], 0)

    def test_not_found(self):
        res = self.client.get("/api/people/999999/")

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", res.data)

    def test_public_and_read_only(self):
        url = f"/api/people/{self.tom.id}/"

        self.assertEqual(self.client.get(url).status_code, 200)
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                res = getattr(self.client, method)(url)

                self.assertEqual(
                    res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
                )
