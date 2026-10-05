from django.contrib.auth.models import AbstractUser
from rest_framework import serializers

from movie.models import Movie, Genre, MovieCast, Rating, Comment


class ImageConfigSerializer(serializers.Serializer):
    base_url = serializers.CharField()
    poster_sizes = serializers.ListField(child=serializers.CharField())
    backdrop_sizes = serializers.ListField(child=serializers.CharField())
    profile_sizes = serializers.ListField(child=serializers.CharField())


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name")


class MovieCastSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="person.name")
    profile_path = serializers.CharField(source="person.profile_path")

    class Meta:
        model = MovieCast
        fields = ("id", "name", "profile_path", "character", "order")


class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = (
            "id",
            "title",
            "genres",
            "release_date",
            "runtime",
            "vote_average",
            "vote_count",
            "popularity",
            "poster_path",
        )


class MovieListSerializer(MovieSerializer):
    genres = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="name"
    )

    class Meta:
        model = Movie
        fields = (
            "id",
            "title",
            "genres",
            "release_date",
            "vote_average",
            "poster_path",
        )


class MovieDetailSerializer(MovieSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    cast = MovieCastSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    ratings_count = serializers.IntegerField(read_only=True)
    trailer_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Movie
        fields = (
            "id",
            "title",
            "genres",
            "cast",
            "release_date",
            "overview",
            "runtime",
            "vote_average",
            "poster_path",
            "backdrop_path",
            "average_rating",
            "ratings_count",
            "trailer_url",
        )

    def get_trailer_url(self, obj) -> str | None:
        if not obj.trailer_youtube_id:
            return None

        return "https://www.youtube.com/watch?v=" + obj.trailer_youtube_id


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ("score",)
        extra_kwargs = {"score": {"min_value": 1, "max_value": 5}}

    def validate_score(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Score must be between 1 and 5")
        return value


class InWatchlistSerializer(serializers.Serializer):
    in_watchlist = serializers.BooleanField(read_only=True)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "movie",
            "text",
            "created_at",
            "parent",
            "author",
            "likes_count",
            "is_liked",
        )

    def get_author(self, obj) -> str:
        if obj.user.first_name and obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}"

        if obj.user.first_name:
            return f"{obj.user.first_name}"

        else:
            return f"User{obj.user.id}"

    def validate(self, attrs):
        parent_comment = attrs.get("parent")
        movie = attrs.get("movie")

        if not parent_comment:
            return attrs

        if parent_comment.movie.id != movie.id:
            raise serializers.ValidationError(
                "Parent comment must belong to the same movie"
            )

        if parent_comment.parent:
            raise serializers.ValidationError("Cannot reply to a reply")

        return attrs


class CommentLikeStatusSerializer(serializers.Serializer):
    liked = serializers.BooleanField(read_only=True)
