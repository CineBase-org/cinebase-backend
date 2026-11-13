from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase

from movie.constants import (
    BACKDROP_SIZES,
    POSTER_SIZES,
    PROFILE_SIZES,
    TMDB_IMAGE_BASE_URL,
)


class ImageConfigTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/config/images/"

    def test_available_without_token(self):
        res = self.client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_returns_base_url_and_sizes(self):
        res = self.client.get(self.url)

        self.assertEqual(
            res.data,
            {
                "base_url": TMDB_IMAGE_BASE_URL,
                "poster_sizes": POSTER_SIZES,
                "backdrop_sizes": BACKDROP_SIZES,
                "profile_sizes": PROFILE_SIZES,
            },
        )

    def test_base_url_ends_with_slash_for_building_links(self):
        res = self.client.get(self.url)

        self.assertTrue(res.data["base_url"].startswith("https://"))
        self.assertTrue(res.data["base_url"].endswith("/"))

    def test_sizes_are_non_empty_lists_of_strings(self):
        res = self.client.get(self.url)

        for key in ("poster_sizes", "backdrop_sizes", "profile_sizes"):
            with self.subTest(key=key):
                self.assertIsInstance(res.data[key], list)
                self.assertTrue(res.data[key])
                self.assertTrue(all(isinstance(s, str) for s in res.data[key]))

    def test_original_size_is_available_for_every_image_kind(self):
        res = self.client.get(self.url)

        for key in ("poster_sizes", "backdrop_sizes", "profile_sizes"):
            with self.subTest(key=key):
                self.assertIn("original", res.data[key])

    def test_only_get_is_allowed(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                res = getattr(self.client, method)(self.url)

                self.assertEqual(
                    res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
                )
