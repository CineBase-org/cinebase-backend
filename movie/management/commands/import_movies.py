import os
import json
import urllib.parse
import urllib.request

from django.core.management import BaseCommand

from movie.models import Movie, Genre, Person, MovieCast

API_KEY = os.environ.get("API_KEY")
BASE_URL = "https://api.themoviedb.org/3"


def get_popular_page(page):
    params = urllib.parse.urlencode(
        {"api_key": API_KEY, "language": "en-US", "page": page}
    )
    url = f"{BASE_URL}/movie/popular?{params}"

    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def get_movie_details(movie_id):
    params = urllib.parse.urlencode(
        {
            "api_key": API_KEY,
            "language": "en-US",
            "append_to_response": "credits,videos",
        }
    )
    url = f"{BASE_URL}/movie/{movie_id}?{params}"

    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def pick_trailer_key(videos: list):
    for video in videos:
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            return video.get("key")
    return None


def save_movie(movie_data):
    movie, created = Movie.objects.get_or_create(
        tmdb_id=movie_data["id"],
        defaults={
            "title": movie_data["title"],
            "overview": movie_data["overview"],
            "release_date": movie_data["release_date"] or None,
            "vote_average": movie_data["vote_average"],
            "vote_count": movie_data["vote_count"],
            "popularity": movie_data["popularity"],
            "poster_path": movie_data["poster_path"],
            "backdrop_path": movie_data["backdrop_path"],
        },
    )

    details = get_movie_details(movie_data["id"])

    movie.runtime = details["runtime"]
    movie.trailer_youtube_id = pick_trailer_key(details["videos"]["results"])
    movie.save()

    genre_objects = []
    for genre in details["genres"]:
        genre, _ = Genre.objects.get_or_create(
            tmdb_id=genre["id"],
            defaults={
                "name": genre["name"],
            },
        )
        genre_objects.append(genre)
    movie.genres.set(genre_objects)

    for cast_member in details["credits"]["cast"][:10]:
        person, _ = Person.objects.get_or_create(
            tmdb_id=cast_member["id"],
            defaults={
                "name": cast_member["name"],
                "profile_path": cast_member["profile_path"],
            },
        )
        MovieCast.objects.get_or_create(
            movie=movie,
            person=person,
            defaults={
                "character": cast_member["character"],
                "order": cast_member["order"],
            },
        )
        return created


class Command(BaseCommand):
    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0
        for page in range(1, 251):
            data = get_popular_page(page)
            self.stdout.write(self.style.SUCCESS(f"Page: {page}/250"))
            for movie_data in data["results"]:
                created = save_movie(movie_data)
                if created:
                    created_count += 1
                else:
                    existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} movies, {existing_count} already existed"
            )
        )
