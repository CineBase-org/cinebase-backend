import io
import urllib.error
import urllib.parse
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from movie.constants import TMDB_IMAGE_BASE_URL
from movie.management.commands import import_movies
from movie.management.commands.import_movies import (
    fetch_json,
    get_movies_page,
    pick_trailer_key,
    save_movie,
)
from movie.models import Genre, Movie, MovieCast, Person

MODULE = "movie.management.commands.import_movies"


def movie_item(tmdb_id=1, **params):
    """One movie as TMDB returns it in a list page"""
    item = {
        "id": tmdb_id,
        "title": f"Movie {tmdb_id}",
        "overview": "Overview",
        "release_date": "2024-05-01",
        "vote_average": 7.5,
        "vote_count": 100,
        "popularity": 50.5,
        "poster_path": f"/poster{tmdb_id}.jpg",
        "backdrop_path": f"/backdrop{tmdb_id}.jpg",
    }
    item.update(params)
    return item


def movie_details(**params):
    """Details of one movie as TMDB returns them"""
    details = {
        "runtime": 120,
        "genres": [],
        "credits": {"cast": []},
        "videos": {"results": []},
        "watch/providers": {"results": {}},
    }
    details.update(params)
    return details


def parse_page(url):
    query = urllib.parse.urlparse(url).query
    return urllib.parse.parse_qs(query)["page"][0]


def http_error(code):
    return urllib.error.HTTPError("http://tmdb", code, "error", {}, None)


class FakeTmdb:
    """Replaces fetch_json: answers list pages and movie details.

    pages: {page number: [movie items]}
    details: {movie id: details}, movies without details get empty ones
    errors: {("page", 2): exception, ("movie", 5): exception}
    """

    def __init__(self, pages=None, details=None, errors=None):
        self.pages = pages or {}
        self.details = details or {}
        self.errors = errors or {}
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path.endswith(("/movie/popular", "/discover/movie")):
            page = int(params["page"][0])
            if ("page", page) in self.errors:
                raise self.errors[("page", page)]
            return {"results": self.pages.get(page, [])}

        movie_id = int(parsed.path.rsplit("/", 1)[1])
        if ("movie", movie_id) in self.errors:
            raise self.errors[("movie", movie_id)]
        return self.details.get(movie_id, movie_details())


class PickTrailerKeyTests(TestCase):
    def test_takes_first_youtube_trailer(self):
        videos = [
            {"site": "Vimeo", "type": "Trailer", "key": "vimeo"},
            {"site": "YouTube", "type": "Teaser", "key": "teaser"},
            {"site": "YouTube", "type": "Trailer", "key": "first"},
            {"site": "YouTube", "type": "Trailer", "key": "second"},
        ]

        self.assertEqual(pick_trailer_key(videos), "first")

    def test_none_without_suitable_video(self):
        videos = [{"site": "YouTube", "type": "Clip", "key": "clip"}]

        self.assertIsNone(pick_trailer_key(videos))

    def test_none_for_empty_list(self):
        self.assertIsNone(pick_trailer_key([]))


@mock.patch(f"{MODULE}.time.sleep")
@mock.patch(f"{MODULE}.urllib.request.urlopen")
class FetchJsonTests(TestCase):
    @staticmethod
    def response(body=b'{"ok": true}'):
        response = mock.MagicMock()
        response.read.return_value = body
        response.__enter__.return_value = response
        return response

    def test_returns_parsed_json(self, urlopen, sleep):
        urlopen.return_value = self.response(b'{"page": 1}')

        self.assertEqual(fetch_json("http://tmdb"), {"page": 1})
        sleep.assert_not_called()

    def test_retries_temporary_errors_and_waits_longer_each_time(
        self, urlopen, sleep
    ):
        urlopen.side_effect = [
            http_error(429),
            http_error(503),
            urllib.error.URLError("network"),
            self.response(),
        ]

        self.assertEqual(fetch_json("http://tmdb"), {"ok": True})

        self.assertEqual(urlopen.call_count, 4)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list], [1, 2, 4]
        )

    def test_does_not_retry_not_found(self, urlopen, sleep):
        urlopen.side_effect = http_error(404)

        with self.assertRaises(urllib.error.HTTPError) as caught:
            fetch_json("http://tmdb")

        self.assertEqual(caught.exception.code, 404)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_gives_up_after_max_retries(self, urlopen, sleep):
        urlopen.side_effect = http_error(500)

        with self.assertRaises(urllib.error.HTTPError):
            fetch_json("http://tmdb")

        self.assertEqual(urlopen.call_count, import_movies.MAX_RETRIES)

    def test_retries_timeouts(self, urlopen, sleep):
        urlopen.side_effect = [TimeoutError(), self.response()]

        self.assertEqual(fetch_json("http://tmdb"), {"ok": True})


class GetMoviesPageTests(TestCase):
    def get_params(self, source, page=3):
        fake = FakeTmdb(pages={page: []})
        with mock.patch(f"{MODULE}.fetch_json", fake):
            get_movies_page(source, page)
        parsed = urllib.parse.urlparse(fake.urls[0])
        return parsed.path, urllib.parse.parse_qs(parsed.query)

    def test_popular_source(self):
        path, params = self.get_params("popular")

        self.assertEqual(path, "/3/movie/popular")
        self.assertEqual(params["page"], ["3"])
        self.assertEqual(params["language"], ["en-US"])

    def test_new_source_asks_for_recent_releases(self):
        path, params = self.get_params("new")

        self.assertEqual(path, "/3/discover/movie")
        self.assertEqual(params["sort_by"], ["popularity.desc"])
        self.assertEqual(params["include_adult"], ["false"])
        self.assertLess(
            params["primary_release_date.gte"],
            params["primary_release_date.lte"],
        )


class SaveMovieTests(TestCase):
    def save(self, item=None, details=None):
        item = item or movie_item()
        fake = FakeTmdb(details={item["id"]: details or movie_details()})
        with mock.patch(f"{MODULE}.fetch_json", fake):
            return save_movie(item)

    def test_creates_movie_from_list_and_details(self):
        created = self.save(details=movie_details(runtime=95))

        self.assertTrue(created)
        movie = Movie.objects.get(tmdb_id=1)
        self.assertEqual(movie.title, "Movie 1")
        self.assertEqual(movie.overview, "Overview")
        self.assertEqual(str(movie.release_date), "2024-05-01")
        self.assertEqual(movie.vote_count, 100)
        self.assertEqual(movie.poster_path, "/poster1.jpg")
        self.assertEqual(movie.backdrop_path, "/backdrop1.jpg")
        self.assertEqual(movie.runtime, 95)

    def test_empty_release_date_becomes_null(self):
        self.save(movie_item(release_date=""))

        self.assertIsNone(Movie.objects.get(tmdb_id=1).release_date)

    def test_existing_movie_is_updated_not_duplicated(self):
        self.save()

        created = self.save(movie_item(title="New title", vote_count=500))

        self.assertFalse(created)
        self.assertEqual(Movie.objects.count(), 1)
        movie = Movie.objects.get()
        self.assertEqual(movie.title, "New title")
        self.assertEqual(movie.vote_count, 500)

    def test_trailer_is_saved(self):
        self.save(
            details=movie_details(
                videos={
                    "results": [
                        {"site": "YouTube", "type": "Trailer", "key": "abc"}
                    ]
                }
            )
        )

        self.assertEqual(Movie.objects.get().trailer_youtube_id, "abc")

    def test_genres_are_created_once_and_linked(self):
        details = movie_details(
            genres=[{"id": 28, "name": "Action"}, {"id": 18, "name": "Drama"}]
        )
        self.save(movie_item(1), details)
        self.save(movie_item(2), details)

        self.assertEqual(Genre.objects.count(), 2)
        names = Movie.objects.get(tmdb_id=2).genres.values_list(
            "name", flat=True
        )
        self.assertEqual(sorted(names), ["Action", "Drama"])

    def test_genres_follow_the_latest_details(self):
        self.save(details=movie_details(genres=[{"id": 28, "name": "Action"}]))

        self.save(details=movie_details(genres=[{"id": 18, "name": "Drama"}]))

        self.assertEqual(
            list(Movie.objects.get().genres.values_list("name", flat=True)),
            ["Drama"],
        )

    def test_only_first_five_cast_members_are_saved(self):
        cast = [
            {
                "id": number,
                "name": f"Actor {number}",
                "profile_path": None,
                "character": f"Role {number}",
                "order": number,
            }
            for number in range(8)
        ]

        self.save(details=movie_details(credits={"cast": cast}))

        self.assertEqual(MovieCast.objects.count(), 5)
        self.assertEqual(Person.objects.count(), 5)
        self.assertFalse(Person.objects.filter(tmdb_id=5).exists())

    def test_importing_twice_does_not_duplicate_cast(self):
        cast = [
            {
                "id": 1,
                "name": "Actor",
                "profile_path": "/a.jpg",
                "character": "Hero",
                "order": 0,
            }
        ]
        details = movie_details(credits={"cast": cast})
        self.save(details=details)

        self.save(details=details)

        self.assertEqual(MovieCast.objects.count(), 1)
        self.assertEqual(Person.objects.count(), 1)

    def providers(self, **countries):
        return movie_details(**{"watch/providers": {"results": countries}})

    def test_streaming_platforms_from_the_us_only(self):
        self.save(
            details=self.providers(
                US={
                    "flatrate": [
                        {
                            "provider_id": 8,
                            "provider_name": "Netflix",
                            "logo_path": "/n.jpg",
                        }
                    ]
                },
                DE={
                    "flatrate": [
                        {
                            "provider_id": 9,
                            "provider_name": "German Only",
                            "logo_path": "/g.jpg",
                        }
                    ]
                },
            )
        )

        self.assertEqual(
            Movie.objects.get().streaming_platforms,
            [
                {
                    "id": 8,
                    "name": "Netflix",
                    "logo_url": f"{TMDB_IMAGE_BASE_URL}w92/n.jpg",
                }
            ],
        )

    def test_platform_in_several_types_is_listed_once(self):
        platform = {
            "provider_id": 8,
            "provider_name": "Netflix",
            "logo_path": "/n.jpg",
        }
        self.save(
            details=self.providers(
                US={"flatrate": [platform], "rent": [platform], "buy": []}
            )
        )

        self.assertEqual(len(Movie.objects.get().streaming_platforms), 1)

    def test_platform_without_logo_has_null_logo_url(self):
        self.save(
            details=self.providers(
                US={
                    "rent": [
                        {
                            "provider_id": 3,
                            "provider_name": "No Logo",
                            "logo_path": None,
                        }
                    ]
                }
            )
        )

        platform = Movie.objects.get().streaming_platforms[0]
        self.assertIsNone(platform["logo_url"])

    def test_no_providers_gives_empty_list(self):
        self.save(details=movie_details(**{"watch/providers": {}}))

        self.assertEqual(Movie.objects.get().streaming_platforms, [])


@mock.patch(f"{MODULE}.time.sleep")
class ImportCommandTests(TestCase):
    def imported_ids(self):
        return list(Movie.objects.values_list("tmdb_id", flat=True))

    def run_import(self, fake, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch(f"{MODULE}.fetch_json", fake):
            call_command("import_movies", *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_imports_requested_pages(self, sleep):
        fake = FakeTmdb(
            pages={1: [movie_item(1), movie_item(2)], 2: [movie_item(3)]}
        )

        out, _ = self.run_import(fake, "--pages", "2")

        self.assertEqual(Movie.objects.count(), 3)
        self.assertIn("Created 3 movies, 0 already existed", out)

    def test_second_run_counts_existing_movies(self, sleep):
        fake = FakeTmdb(pages={1: [movie_item(1), movie_item(2)]})
        self.run_import(fake, "--pages", "1")

        out, _ = self.run_import(fake, "--pages", "1")

        self.assertEqual(Movie.objects.count(), 2)
        self.assertIn("Created 0 movies, 2 already existed", out)

    def test_start_page_resumes_the_import(self, sleep):
        fake = FakeTmdb(pages={1: [movie_item(1)], 2: [movie_item(2)]})

        self.run_import(fake, "--start-page", "2", "--pages", "1")

        self.assertEqual(self.imported_ids(), [2])

    def test_pages_are_limited_to_the_last_page_of_tmdb(self, sleep):
        fake = FakeTmdb()

        self.run_import(fake, "--start-page", "249", "--pages", "5")

        requested = [
            int(parse_page(url)) for url in fake.urls
        ]
        self.assertEqual(requested, [249, 250])

    def test_new_source_uses_discover(self, sleep):
        fake = FakeTmdb(pages={1: [movie_item(1)]})

        self.run_import(fake, "--source", "new", "--pages", "1")

        self.assertIn("/discover/movie", fake.urls[0])
        self.assertEqual(Movie.objects.count(), 1)

    def test_invalid_arguments(self, sleep):
        for args in (("--pages", "0"), ("--start-page", "0")):
            with self.subTest(args=args):
                with self.assertRaises(CommandError):
                    self.run_import(FakeTmdb(), *args)

    def test_movie_missing_in_tmdb_is_skipped_without_failure(self, sleep):
        fake = FakeTmdb(
            pages={1: [movie_item(1), movie_item(2)]},
            errors={("movie", 1): http_error(404)},
        )

        out, _ = self.run_import(fake, "--pages", "1")

        self.assertEqual(self.imported_ids(), [2])
        self.assertIn("Not found in TMDB, skipped: 1", out)
        self.assertIn("1 not found in TMDB, 0 failed", out)

    def test_failed_movie_does_not_stop_the_import_but_fails_the_command(
        self, sleep
    ):
        fake = FakeTmdb(
            pages={1: [movie_item(1), movie_item(2)]},
            errors={("movie", 1): ValueError("broken data")},
        )

        with self.assertRaisesMessage(CommandError, "1 failures"):
            self.run_import(fake, "--pages", "1")

        # the movie without the error was still imported
        self.assertEqual(self.imported_ids(), [2])

    def test_failed_movie_is_rolled_back(self, sleep):
        fake = FakeTmdb(
            pages={1: [movie_item(1)]},
            errors={("movie", 1): ValueError("broken data")},
        )

        with self.assertRaises(CommandError):
            self.run_import(fake, "--pages", "1")

        # the movie row saved before the details failed is not left behind
        self.assertFalse(Movie.objects.exists())

    def test_failed_page_is_skipped_and_reported(self, sleep):
        fake = FakeTmdb(
            pages={2: [movie_item(2)]},
            errors={("page", 1): ValueError("page down")},
        )
        out, err = io.StringIO(), io.StringIO()

        with mock.patch(f"{MODULE}.fetch_json", fake):
            with self.assertRaisesMessage(CommandError, "1 failures"):
                call_command(
                    "import_movies", "--pages", "2", stdout=out, stderr=err
                )

        self.assertIn("Skipped page 1", err.getvalue())
        self.assertEqual(self.imported_ids(), [2])
