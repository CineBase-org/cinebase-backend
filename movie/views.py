from django.db.models import Avg, Count, Exists, OuterRef, Value, BooleanField
from django.db.models.functions import Round
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
)
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from movie.constants import (
    TMDB_IMAGE_BASE_URL,
    POSTER_SIZES,
    BACKDROP_SIZES,
    PROFILE_SIZES,
)
from movie.models import Movie, Rating, Watchlist, Comment, CommentLike
from movie.permissions import IsAdminOrReadOnly, IsAuthorOrAdminOrReadOnly
from movie.serializers import (
    MovieListSerializer,
    MovieDetailSerializer,
    ImageConfigSerializer,
    RatingSerializer,
    InWatchlistSerializer,
    CommentSerializer,
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

        if self.action == "retrieve":
            queryset = queryset.annotate(
                average_rating=Round(Avg("ratings__score"), 1),
                ratings_count=Count("ratings", distinct=True),
            ).prefetch_related("cast__person")
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return MovieListSerializer

        if self.action == "retrieve":
            return MovieDetailSerializer

        return MovieDetailSerializer

    @extend_schema(
        request=RatingSerializer,
        responses=RatingSerializer,
    )
    @action(
        methods=["get", "put", "delete"],
        detail=True,
        url_path="rating",
        permission_classes=[IsAuthenticated],
    )
    def rating(self, request, pk=None):
        user = self.request.user
        movie = self.get_object()

        if request.method == "GET":
            rating = Rating.objects.filter(user=user, movie=movie).first()
            if not rating:
                return Response({"score": None})
            return Response(RatingSerializer(rating).data)

        if request.method == "PUT":
            validated_rating = RatingSerializer(data=request.data)
            validated_rating.is_valid(raise_exception=True)

            score = validated_rating.validated_data["score"]
            rating, created = Rating.objects.update_or_create(
                user=user, movie=movie, defaults={"score": score}
            )

            return Response(
                RatingSerializer(rating).data,
                status=(
                    status.HTTP_201_CREATED if created else status.HTTP_200_OK
                ),
            )

        if request.method == "DELETE":
            rating = Rating.objects.filter(user=user, movie=movie).first()
            if not rating:
                return Response(status=status.HTTP_404_NOT_FOUND)
            rating.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        responses=InWatchlistSerializer,
    )
    @action(
        methods=["get", "put", "delete"],
        detail=True,
        url_path="watchlist",
        permission_classes=[IsAuthenticated],
    )
    def watchlist(self, request, pk=None):
        user = self.request.user
        movie = self.get_object()

        if request.method == "GET":
            in_watchlist = Watchlist.objects.filter(
                user=user, movie=movie
            ).first()
            if not in_watchlist:
                return Response(
                    {"in_watchlist": False}, status=status.HTTP_200_OK
                )
            return Response({"in_watchlist": True}, status=status.HTTP_200_OK)

        if request.method == "PUT":

            in_watchlist, created = Watchlist.objects.get_or_create(
                user=user,
                movie=movie,
            )
            return Response(
                {"in_watchlist": True},
                status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        if request.method == "DELETE":
            in_watchlist = Watchlist.objects.filter(
                user=user, movie=movie
            ).first()
            if not in_watchlist:
                return Response(status=status.HTTP_404_NOT_FOUND)
            in_watchlist.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


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


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="movie",
                description="Movie id to filter comments by",
                required=False,
                type=int,
            )
        ]
    )
)
class CommentViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Comment.objects.select_related("user").annotate(
        likes_count=Count("likes", distinct=True)
    )
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrAdminOrReadOnly]

    def get_queryset(self):
        queryset = self.queryset

        movie = self.request.query_params.get("movie")

        if movie:
            queryset = queryset.filter(movie_id=movie)

        if self.request.user.is_authenticated:
            liked = CommentLike.objects.filter(
                user=self.request.user,
                comment=OuterRef("pk"),
            )
            queryset = queryset.annotate(is_liked=Exists(liked))
        else:
            queryset = queryset.annotate(
                is_liked=Value(False, output_field=BooleanField())
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(
        methods=["get", "put", "delete"],
        detail=True,
        url_path="likes",
        permission_classes=[
            IsAuthenticated,
        ],
    )
    def likes(self, request, pk=None):
        user = self.request.user
        comment = self.get_object()

        if request.method == "PUT":
            liked, created = CommentLike.objects.get_or_create(
                user=user, comment=comment
            )
            return Response(
                {"liked": True},
                status=(
                    status.HTTP_201_CREATED if created else status.HTTP_200_OK
                ),
            )

        if request.method == "DELETE":
            like = CommentLike.objects.filter(
                user=user, comment=comment
            ).first()
            if not like:
                return Response({"liked": False}, status=status.HTTP_200_OK)
            like.delete()
            return Response({"liked": False}, status=status.HTTP_200_OK)
