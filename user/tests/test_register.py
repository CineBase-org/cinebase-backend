from django.contrib.auth import get_user_model
from rest_framework import status

from user.models import UserProfile
from user.tests.helpers import BaseApiTestCase, create_user


class RegisterBaseTestCase(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        self.url = "/api/user/register/"
        self.payload = {"email": "user@user.com", "password": "useruser"}


class RegisterTests(RegisterBaseTestCase):
    def test_register_user(self):
        res = self.client.post(self.url, self.payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("email", res.data)
        self.assertIn("id", res.data)
        self.assertNotIn("password", res.data)
        self.assertTrue(
            get_user_model().objects.filter(email="user@user.com").exists(), 1
        )
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_register_hashes_password(self):
        res = self.client.post(self.url, self.payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(email="user@user.com")
        self.assertNotEqual(user.password, "useruser")
        self.assertTrue(user.check_password("useruser"))

    def test_register_creates_profile(self):
        res = self.client.post(self.url, self.payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(email="user@user.com")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_register_duplicate_email(self):
        create_user(self.payload["email"], self.payload["password"])
        res = self.client.post(self.url, self.payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res.data)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_register_invalid_data(self):
        res1 = self.client.post(self.url, {"email": "test@test.com"})
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        res2 = self.client.post(self.url, {"password": "testetst"})
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        res3 = self.client.post(
            self.url, {"email": "testtest", "password": "testtest"}
        )
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_register_short_password(self):
        res = self.client.post(
            self.url, {"email": "test@test.com", "password": "saxx"}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_register_cannot_set_staff(self):
        res = self.client.post(
            self.url,
            {
                "email": "user@user.com",
                "password": "useruser",
                "is_staff": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(res.data["is_staff"])
        self.assertFalse(
            get_user_model().objects.filter(is_staff=True).exists()
        )
