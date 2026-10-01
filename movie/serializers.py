from rest_framework import serializers
from movie.models import Movie, Genre, MovieCast


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
        )
