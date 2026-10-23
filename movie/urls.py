from django.urls import path, include
from rest_framework import routers

from movie.views import (
    MovieViewSet,
    ImageConfigView,
    CommentViewSet,
    GenresListView,
)

router = routers.DefaultRouter()
router.register("movies", MovieViewSet)
router.register("comments", CommentViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("config/images/", ImageConfigView.as_view(), name="image_config"),
    path("genres/", GenresListView.as_view(), name="genres"),
]

app_name = "movie"
