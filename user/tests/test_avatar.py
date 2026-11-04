import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status

from user.tests.helpers import BaseApiTestCase, create_user, create_image

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class AvatarTests(BaseApiTestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.user = create_user()
        self.url = "/api/user/me/"
        self.client.force_authenticate(user=self.user)

    def upload(self, file):
        return self.client.patch(
            self.url, {"avatar": file}, format="multipart"
        )

    def test_profile_without_avatar_is_null(self):
        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["avatar"])

    def test_upload_avatar(self):
        res = self.upload(create_image())

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["avatar"].endswith(".png"))
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.avatar)

    def test_upload_allowed_formats(self):
        for image_format, extension in (
            ("PNG", "png"),
            ("JPEG", "jpg"),
            ("WEBP", "webp"),
        ):
            with self.subTest(image_format=image_format):
                res = self.upload(create_image(f"a.{extension}", image_format))
                self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_upload_too_large(self):
        with mock.patch("user.serializers.MAX_AVATAR_SIZE", 10):
            res = self.upload(create_image())

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("avatar", res.data)

    def test_upload_unsupported_format(self):
        res = self.upload(create_image("a.gif", "GIF"))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("avatar", res.data)

    def test_upload_not_an_image(self):
        fake = SimpleUploadedFile(
            "a.png", b"not an image", content_type="image/png"
        )

        res = self.upload(fake)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("avatar", res.data)

    def test_remove_avatar(self):
        self.upload(create_image())

        res = self.client.patch(self.url, {"avatar": None}, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["avatar"])
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)
