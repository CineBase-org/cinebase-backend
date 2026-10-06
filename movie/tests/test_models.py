from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from movie.models import Movie, Rating, Watchlist

from movie.tests.helpers import BaseApiTestCase


class RatingConstraintTests(BaseApiTestCase):
    def test_score_out_of_range_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Rating.objects.create(
                    user=self.user, movie=self.movie, score=10
                )


class WatchlistConstraintTests(BaseApiTestCase):
    def test_duplicate_watchlist_entry_raises_integrity_error(self):
        Watchlist.objects.create(movie=self.movie, user=self.user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Watchlist.objects.create(movie=self.movie, user=self.user)
