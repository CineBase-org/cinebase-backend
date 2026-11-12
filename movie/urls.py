from django.urls import path, include
from rest_framework import routers

from movie.views import (
    MovieViewSet,
    ImageConfigView,
    CommentViewSet,
    GenresListView,
    WatchlistListView,
)

router = routers.DefaultRouter()
router.register("movies", MovieViewSet)
router.register("comments", CommentViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("config/images/", ImageConfigView.as_view(), name="image_config"),
    path("genres/", GenresListView.as_view(), name="genres"),
    path("watchlist/", WatchlistListView.as_view(), name="watchlist"),
]

app_name = "movie"
