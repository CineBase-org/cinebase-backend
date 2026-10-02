from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
)
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from movie.constants import (
    TMDB_IMAGE_BASE_URL,
    POSTER_SIZES,
    BACKDROP_SIZES,
    PROFILE_SIZES,
)
from movie.models import Movie
from movie.permissions import IsAdminOrReadOnly
from movie.serializers import (
    MovieListSerializer,
    MovieDetailSerializer,
    ImageConfigSerializer,
)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="genres",
                description="Comma-separated genre ids to filter by, e.g. 1,5,12",
                required=False,
                type=str,
            )
        ]
    )
)
class MovieViewSet(viewsets.ModelViewSet):
    queryset = Movie.objects.prefetch_related("genres")
    serializer_class = MovieListSerializer
    permission_classes = [IsAdminOrReadOnly]

    @staticmethod
    def _params_to_ints(qs):
        """Converts a list of string IDs to a list of integers"""
        return [int(str_id) for str_id in qs.split(",")]

    def get_queryset(self):
        genres = self.request.query_params.get("genres")
        queryset = self.queryset

        if genres:
            genres_ids = self._params_to_ints(genres)
            queryset = queryset.filter(genres__id__in=genres_ids)

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return MovieListSerializer

        if self.action == "retrieve":
            return MovieDetailSerializer

        return MovieDetailSerializer


class ImageConfigView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get image configuration",
        description="Returns the base URL and the list of supported image sizes. "
        "To build a full image link, combine: base_url + size + image path "
        "from a movie or actor (poster_path, backdrop_path, profile_path). "
        "Example: https://image.tmdb.org/t/p/ + w500 + /abc123.jpg",
        responses={200: ImageConfigSerializer},
    )
    def get(self, request):
        return Response(
            {
                "base_url": TMDB_IMAGE_BASE_URL,
                "poster_sizes": POSTER_SIZES,
                "backdrop_sizes": BACKDROP_SIZES,
                "profile_sizes": PROFILE_SIZES,
            }
        )
