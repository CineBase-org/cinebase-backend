from django.db.models import Avg, Count, Exists, OuterRef, Value, BooleanField
from django.db.models.functions import Round
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
)
from rest_framework import viewsets, status, mixins, generics
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
from movie.models import Movie, Rating, Watchlist, Comment, CommentLike, Genre
from movie.permissions import IsAdminOrReadOnly, IsAuthorOrAdminOrReadOnly
from movie.serializers import (
    MovieListSerializer,
    MovieDetailSerializer,
    ImageConfigSerializer,
    RatingSerializer,
    InWatchlistSerializer,
    CommentSerializer,
    CommentLikeStatusSerializer,
    GenreSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List all movies",
        description="Paginated list of movies, most popular first. "
        "Each item has a short set of fields for catalog cards. "
        "Use ?genres=1,5 to filter by one or more genre ids "
        "and ?page=N to change the page."
        "Use ?search=dune to find movies by title.",
        parameters=[
            OpenApiParameter(
                name="genres",
                description="Comma-separated genre ids to filter by, e.g. 1,5,12",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="search",
                description="Case-insensitive part of the movie title, e.g. dune",
                required=False,
                type=str,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get movie details",
        description="Full movie data for the movie page: "
        "overview, genres, cast, poster and backdrop paths. "
        "average_rating is the average of ratings given by users of this site "
        "(1-5, rounded to one decimal) "
        "and is null if nobody has rated the movie yet; "
        "vote_average is the TMDB rating (0-10). "
        "trailer_url is a YouTube link, or null if the movie has no trailer.",
    ),
    create=extend_schema(
        summary="Create a movie (admin only)",
        description="Admin only. Create a movie manually "
        "(normally movies are imported from TMDB).",
    ),
    update=extend_schema(
        summary="Replace a movie (admin only)",
        description="Admin only. Replace all editable fields of a movie.",
    ),
    partial_update=extend_schema(
        summary="Update a movie (admin only)",
        description="Admin only. Update only the provided fields of a movie.",
    ),
    destroy=extend_schema(
        summary="Delete a movie (admin only)",
        description="Admin only. Delete a movie together with its ratings, "
        "comments and watchlist entries.",
    ),
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
        queryset = self.queryset

        genres = self.request.query_params.get("genres")
        search = self.request.query_params.get("search", "").strip()

        if search:
            queryset = queryset.filter(title__icontains=search)

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
        methods=["get"],
        request=None,
        responses={status.HTTP_200_OK: RatingSerializer},
        summary="Get my rating of a movie",
        description="Get the current user's rating for a movie. "
        "Returns {'score': null} "
        "if the user has not rated it yet.",
    )
    @extend_schema(
        methods=["put"],
        request=RatingSerializer,
        responses={
            status.HTTP_200_OK: RatingSerializer,
            status.HTTP_201_CREATED: RatingSerializer,
        },
        summary="Rate a movie",
        description="Rate a movie from 1 to 5. "
        "Returns 201 if the rating was created, "
        "200 if the existing rating was updated.",
    )
    @extend_schema(
        methods=["delete"],
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_404_NOT_FOUND: None,
        },
        summary="Remove my rating of a movie",
        description="Remove the current user's rating for a movie. "
        "Returns 204 on success, 404 if the user had not rated it.",
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
        methods=["get"],
        request=None,
        responses={
            status.HTTP_200_OK: InWatchlistSerializer,
        },
        summary="Check if a movie is in my watchlist",
        description="Check whether a movie is in the current user's watchlist. "
        "Returns {'in_watchlist': true} or {'in_watchlist': false}.",
    )
    @extend_schema(
        methods=["put"],
        request=None,
        responses={
            status.HTTP_200_OK: InWatchlistSerializer,
            status.HTTP_201_CREATED: InWatchlistSerializer,
        },
        summary="Add a movie to my watchlist",
        description="Add a movie to the current user's watchlist. "
        "Returns 201 if it was added, "
        "200 if it was already in the watchlist.",
    )
    @extend_schema(
        methods=["delete"],
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_404_NOT_FOUND: None,
        },
        summary="Remove a movie from my watchlist",
        description="Remove a movie from the current user's watchlist. "
        "Returns 204 on success, "
        "404 if it was not in the watchlist.",
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
        summary="List all comments",
        description="Paginated list of comments, newest first. "
        "Pass ?movie=<id> to get comments of one movie. "
        "Replies are returned in the same flat list with "
        "the parent field set to the id of the comment they answer. "
        "is_liked is false for anonymous users.",
        parameters=[
            OpenApiParameter(
                name="movie",
                description="Movie id to filter comments by",
                required=False,
                type=int,
            )
        ],
    ),
    create=extend_schema(
        summary="Add a comment",
        description="Authentication required. Send movie and text. "
        "To reply to a comment, also send parent: "
        "the id of a top-level comment of the same movie. "
        "Replies to replies are not allowed.",
    ),
    destroy=extend_schema(
        summary="Delete a comment",
        description="Authentication required. "
        "Only the author of the comment or an admin can delete it.",
    ),
    retrieve=extend_schema(
        summary="Get a comment", description="Return a single comment by id."
    ),
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

    @extend_schema(
        methods=["PUT"],
        request=None,
        responses={
            status.HTTP_201_CREATED: CommentLikeStatusSerializer,
            status.HTTP_200_OK: CommentLikeStatusSerializer,
        },
        summary="Like a comment",
        description="Like a comment. Returns 201 if the like was created, "
        "200 if the comment was already liked by the current user.",
    )
    @extend_schema(
        methods=["DELETE"],
        request=None,
        responses={status.HTTP_200_OK: CommentLikeStatusSerializer},
        summary="Remove my like from a comment",
        description="Remove the current user's like from a comment. "
        "Returns 200 with liked: false, whether the like existed or not.",
    )
    @action(
        methods=["put", "delete"],
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


@extend_schema_view(
    get=extend_schema(
        summary="List all genres",
        description="Returns all genres as a plain array "
        "(no pagination). Use the id of a genre in the genres filter of "
        "GET /api/movies/, e.g. ?genres=1,5.",
    )
)
class GenresListView(generics.ListAPIView):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = [AllowAny]
    pagination_class = None
