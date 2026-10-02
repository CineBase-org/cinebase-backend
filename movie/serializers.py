from rest_framework import serializers

from movie.models import Movie, Genre, MovieCast, Rating


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
        )


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
