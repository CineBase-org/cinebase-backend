from django.contrib.auth import get_user_model
from django.test import TestCase

from user.tests.helpers import create_user


class UserModelTest(TestCase):
    def test_create_user_without_email(self):
        with self.assertRaises(ValueError):
            create_user(email="", password="x")

    def test_create_user_defaults(self):
        user = get_user_model().objects.create_user(
            email="user@example.com", password="adnpass123"
        )
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        admin = get_user_model().objects.create_superuser(
            email="admin@example.com", password="adminpass123"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_create_superuser_with_wrong_flags(self):
        with self.assertRaises(ValueError):
            get_user_model().objects.create_superuser(
                email="admin@example.com",
                password="adminpass123",
                is_staff=False,
            )

        with self.assertRaises(ValueError):
            get_user_model().objects.create_superuser(
                email="admin2@example.com",
                password="adminpass123",
                is_superuser=False,
            )
