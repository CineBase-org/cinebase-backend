import io
import os
import shutil
import tempfile
from unittest import mock

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status

from user.models import UserProfile
from user.tests.helpers import BaseApiTestCase, create_user, create_image


class AvatarTests(BaseApiTestCase):
    def setUp(self):
        super().setUp()
        # Every test has its own folder, so files can be counted
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=self.media_root)
        media.enable()
        self.addCleanup(media.disable)

        self.user = create_user()
        self.url = "/api/user/me/"
        self.client.force_authenticate(user=self.user)

    def upload(self, file):
        return self.client.patch(
            self.url, {"avatar": file}, format="multipart"
        )

    def stored_files(self):
        folder = os.path.join(self.media_root, "avatars")
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def stored_image(self):
        self.user.profile.refresh_from_db()
        with default_storage.open(self.user.profile.avatar.name) as stored:
            return Image.open(io.BytesIO(stored.read()))

    def test_profile_without_avatar_is_null(self):
        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["avatar"])

    def test_upload_avatar(self):
        res = self.upload(create_image())

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["avatar"].endswith(".webp"))
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

    # Storage: one stable WEBP object per user

    def test_key_is_based_on_user_id_with_avatars_prefix(self):
        self.upload(create_image("holiday photo.png"))

        self.user.profile.refresh_from_db()
        self.assertEqual(
            self.user.profile.avatar.name, f"avatars/{self.user.pk}.webp"
        )
        self.assertEqual(self.stored_files(), [f"{self.user.pk}.webp"])

    def test_every_format_is_stored_as_webp(self):
        for image_format, extension in (
            ("PNG", "png"),
            ("JPEG", "jpg"),
            ("WEBP", "webp"),
        ):
            with self.subTest(image_format=image_format):
                self.upload(create_image(f"a.{extension}", image_format))

                self.assertEqual(self.stored_image().format, "WEBP")

    def test_transparency_is_kept(self):
        buffer = io.BytesIO()
        Image.new("RGBA", (10, 10), (255, 0, 0, 0)).save(buffer, "PNG")
        png = SimpleUploadedFile(
            "a.png", buffer.getvalue(), content_type="image/png"
        )

        self.upload(png)

        image = self.stored_image()
        self.assertIn("A", image.getbands())
        self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_size_of_the_picture_is_kept(self):
        self.upload(create_image(size=(40, 25)))

        self.assertEqual(self.stored_image().size, (40, 25))

    def test_camera_rotation_is_applied(self):
        image = Image.new("RGB", (40, 20))
        exif = Image.Exif()
        exif[0x0112] = 6  # rotate 90 degrees to show it right
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", exif=exif)
        photo = SimpleUploadedFile(
            "a.jpg", buffer.getvalue(), content_type="image/jpeg"
        )

        self.upload(photo)

        self.assertEqual(self.stored_image().size, (20, 40))

    def test_exif_is_not_stored(self):
        image = Image.new("RGB", (10, 10))
        exif = Image.Exif()
        exif[0x010F] = "Secret Camera Make"
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", exif=exif)
        photo = SimpleUploadedFile(
            "a.jpg", buffer.getvalue(), content_type="image/jpeg"
        )

        self.upload(photo)

        self.assertEqual(len(self.stored_image().getexif()), 0)

    def test_replace_keeps_one_file(self):
        self.upload(create_image("one.png"))
        self.upload(create_image("two.jpg", "JPEG"))
        self.upload(create_image("three.webp", "WEBP"))

        self.assertEqual(len(self.stored_files()), 1)
        self.user.profile.refresh_from_db()
        self.assertTrue(
            default_storage.exists(self.user.profile.avatar.name)
        )

    def test_remove_deletes_the_file(self):
        self.upload(create_image())

        self.client.patch(self.url, {"avatar": None}, format="json")

        self.assertEqual(self.stored_files(), [])

    def test_old_avatar_with_other_name_is_deleted_on_replace(self):
        # avatars saved before the stable key had random names
        old_name = default_storage.save(
            "avatars/old_random_name.png", SimpleUploadedFile("o.png", b"x")
        )
        UserProfile.objects.filter(user=self.user).update(avatar=old_name)
        # a real request loads the profile from the database, not from a cache
        fresh_user = type(self.user).objects.get(pk=self.user.pk)
        self.client.force_authenticate(user=fresh_user)

        self.upload(create_image())

        self.assertEqual(self.stored_files(), [f"{self.user.pk}.webp"])

    def test_other_fields_do_not_touch_the_avatar(self):
        self.upload(create_image())
        files = self.stored_files()

        res = self.client.patch(self.url, {"bio": "Hi"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self.stored_files(), files)

    def test_users_have_separate_files(self):
        other = create_user(email="other@example.com")
        self.upload(create_image())
        self.client.force_authenticate(user=other)

        self.upload(create_image())

        self.assertEqual(
            self.stored_files(),
            sorted([f"{self.user.pk}.webp", f"{other.pk}.webp"]),
        )
