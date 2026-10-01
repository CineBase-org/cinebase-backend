from django.conf import settings
from django.db import models


class Genre(models.Model):
    tmdb_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Movie(models.Model):
    tmdb_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    genres = models.ManyToManyField(Genre, blank=True)
    release_date = models.DateField(null=True, blank=True)
    overview = models.TextField(blank=True)
    runtime = models.IntegerField(null=True, blank=True)
    vote_average = models.FloatField(default=0)
    vote_count = models.IntegerField(default=0)
    popularity = models.FloatField(default=0)
    poster_path = models.CharField(max_length=255, blank=True, null=True)
    backdrop_path = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.title


class Person(models.Model):
    tmdb_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    profile_path = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class MovieCast(models.Model):
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE, related_name="cast"
    )
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="filmography"
    )
    character = models.CharField(max_length=255)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.character


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist",
    )
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE, related_name="in_watchlist"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "movie"],
                name="unique_user_movie_for_watchlist",
            )
        ]

    def __str__(self):
        return self.movie


class Rating(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE, related_name="ratings"
    )
    score = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(score__gte=1) & models.Q(score__lte=5),
                name="score_range",
            ),
            models.UniqueConstraint(
                fields=["user", "movie"],
                name="unique_user_movie_rating",
            ),
        ]

    def __str__(self):
        return f"{self.movie} - {self.score}"


class Comment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE, related_name="comments"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )


class CommentLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_likes",
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="likes"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "comment"],
                name="unique_user_comment_like",
            )
        ]
