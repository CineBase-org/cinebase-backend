import os
import json
import time
import urllib.parse
import urllib.request
import urllib.error

from django.core.management import BaseCommand, CommandError
from django.db import transaction

from movie.constants import TMDB_IMAGE_BASE_URL
from movie.models import Movie, Genre, Person, MovieCast

API_KEY = os.environ.get("API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
PLATFORMS_COUNTRY = "US"
PLATFORM_TYPES = ("flatrate", "rent", "buy")
PLATFORM_LOGO_SIZE = "w92"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 4
LAST_PAGE = 250


def fetch_json(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(
                url, timeout=REQUEST_TIMEOUT
            ) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if (
                e.code not in (429, 500, 502, 503, 504)
                or attempt == MAX_RETRIES
            ):
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == MAX_RETRIES:
                raise
        time.sleep(2 ** (attempt - 1))


def get_popular_page(page):
    params = urllib.parse.urlencode(
        {"api_key": API_KEY, "language": "en-US", "page": page}
    )
    url = f"{BASE_URL}/movie/popular?{params}"

    return fetch_json(url)


def get_movie_details(movie_id):
    params = urllib.parse.urlencode(
        {
            "api_key": API_KEY,
            "language": "en-US",
            "append_to_response": "credits,videos,watch/providers",
        }
    )
    url = f"{BASE_URL}/movie/{movie_id}?{params}"

    return fetch_json(url)


def pick_trailer_key(videos: list):
    for video in videos:
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            return video.get("key")
    return None


def save_movie(movie_data):
    movie, created = Movie.objects.update_or_create(
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
    providers_data = details.get("watch/providers", {}).get("results", {})
    country_data = providers_data.get(PLATFORMS_COUNTRY, {})
    platforms = {}
    for platform_type in PLATFORM_TYPES:
        for platform in country_data.get(platform_type, []):
            logo_path = platform.get("logo_path")
            platforms[platform["provider_id"]] = {
                "id": platform["provider_id"],
                "name": platform["provider_name"],
                "logo_url": (
                    f"{TMDB_IMAGE_BASE_URL}{PLATFORM_LOGO_SIZE}{logo_path}"
                    if logo_path
                    else None
                ),
            }
    movie.streaming_platforms = list(platforms.values())
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

    for cast_member in details["credits"]["cast"][:5]:
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
    def add_arguments(self, parser):
        parser.add_argument(
            "--start-page",
            type=int,
            default=1,
            help="Page to start from (to resume an interrupted import)",
        )
        parser.add_argument(
            "--pages",
            type=int,
            default=LAST_PAGE,
            help="How many pages to import",
        )

    def handle(self, *args, **options):
        start_page = options["start_page"]
        end_page = min(start_page + options["pages"] - 1, LAST_PAGE)

        if start_page < 1 or options["pages"] < 1:
            raise CommandError("--start-page and --pages must be 1 or more")

        created_count = 0
        existing_count = 0
        failed = []

        for page in range(start_page, end_page + 1):
            try:
                data = get_popular_page(page)
            except Exception as e:
                failed.append(f"page {page}: {e}")
                self.stderr.write(
                    self.style.WARNING(f"Skipped page {page}: {e}")
                )
                continue

            self.stdout.write(self.style.SUCCESS(f"Page: {page}/{end_page}"))

            for movie_data in data["results"]:
                try:
                    with transaction.atomic():
                        created = save_movie(movie_data)
                except Exception as e:
                    failed.append(f"movie {movie_data['id']}: {e}")
                    self.stderr.write(
                        self.style.WARNING(
                            f"Skipped movie {movie_data['id']}: {e}"
                        )
                    )
                    continue

                if created:
                    created_count += 1
                else:
                    existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} movies, "
                f"{existing_count} already existed, {len(failed)} failed"
            )
        )
        for item in failed:
            self.stdout.write(self.style.WARNING(f"  failed: {item}"))
