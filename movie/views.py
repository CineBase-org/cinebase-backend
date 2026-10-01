from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
)
from rest_framework import viewsets

from movie.models import Movie
from movie.permissions import IsAdminOrReadOnly
from movie.serializers import MovieListSerializer, MovieDetailSerializer


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
