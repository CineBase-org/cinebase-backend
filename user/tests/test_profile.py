from datetime import date

from rest_framework import status

from user.tests.helpers import BaseApiTestCase, create_user


class ProfileBaseTestCase(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.url = "/api/user/me/"
        self.client.force_authenticate(user=self.user)


class ProfileTest(ProfileBaseTestCase):
    def test_profile_requires_authentication(self):
        self.client.force_authenticate(user=None)

        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_401_UNAUTHORIZED)

        put_res = self.client.put(self.url)
        self.assertEqual(put_res.status_code, status.HTTP_401_UNAUTHORIZED)

        patch_res = self.client.patch(self.url)
        self.assertEqual(patch_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile(self):
        get_res = self.client.get(self.url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        for key in (
            "first_name",
            "last_name",
            "bio",
            "location",
            "birth_date",
        ):
            self.assertIn(key, get_res.data)
        self.assertEqual(get_res.data["first_name"], "")
        self.assertEqual(get_res.data["last_name"], "")
        self.assertEqual(get_res.data["bio"], "")
        self.assertEqual(get_res.data["location"], "")
        self.assertEqual(get_res.data["birth_date"], None)

    def test_patch_profile_fields(self):
        patch_res = self.client.patch(
            self.url, data={"bio": "test", "location": "test"}
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["bio"], "test")
        self.assertEqual(patch_res.data["location"], "test")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "test")
        self.assertEqual(self.user.profile.location, "test")

    def test_patch_profile_name(self):
        patch_res = self.client.patch(
            self.url, data={"first_name": "A", "last_name": "B"}
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["first_name"], "A")
        self.assertEqual(patch_res.data["last_name"], "B")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "A")
        self.assertEqual(self.user.last_name, "B")

    def test_put_profile(self):
        put_res = self.client.put(
            self.url,
            data={
                "first_name": "A",
                "last_name": "B",
                "bio": "test",
                "location": "test",
                "birth_date": "2000-01-31",
            },
        )
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        for key in (
            "first_name",
            "last_name",
            "bio",
            "location",
            "birth_date",
        ):
            self.assertIn(key, put_res.data)
        self.user.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "A")
        self.assertEqual(self.user.last_name, "B")
        self.assertEqual(self.user.profile.bio, "test")
        self.assertEqual(self.user.profile.location, "test")
        self.assertEqual(self.user.profile.birth_date, date(2000, 1, 31))

    def test_invalid_birth_date(self):
        patch_res = self.client.patch(
            self.url,
            data={
                "birth_date": "not",
            },
        )
        self.assertEqual(patch_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("birth_date", patch_res.data)
