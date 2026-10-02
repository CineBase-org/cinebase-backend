from django.urls import path, include
from rest_framework import routers

from movie.views import MovieViewSet, ImageConfigView

router = routers.DefaultRouter()
router.register("movies", MovieViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("config/images/", ImageConfigView.as_view(), name="image_config"),
]

app_name = "movie"
