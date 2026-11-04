import io

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient


def create_user(email="test@example.com", password="pass12345", **params):
    return get_user_model().objects.create_user(
        email=email, password=password, **params
    )


class BaseApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()


def create_image(name="avatar.png", image_format="PNG", size=(10, 10)):
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format=image_format)
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type=f"image/{image_format.lower()}",
    )
