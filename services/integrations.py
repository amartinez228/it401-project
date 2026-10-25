"""Provider construction and persistent caching; shared by HTML and JSON routes."""
from flask import current_app, g

from services.api_service import RapidApiService
from services.cache_service import cached
from services.imdb_service import ImdbService
from services.scraping_service import BoxOfficeService
from services.streaming_service import StreamingAvailabilityService


def configured(prefix):
    return all(current_app.config.get(f"{prefix}_{part}") for part in ("KEY", "HOST", "BASE_URL"))


def api_client(prefix):
    config = current_app.config
    return RapidApiService(config[f"{prefix}_BASE_URL"], config[f"{prefix}_KEY"], config[f"{prefix}_HOST"])


class MovieSearch:
    def search(self, query, media_type="all"):
        config = current_app.config
        query = " ".join(query.split())
        country = config["RAPIDAPI_COUNTRY"].lower()
        # Include the provider endpoint and country to prevent incompatible cache reuse.
        parameters = {"q": query.casefold(), "type": media_type.lower(), "country": country,
                      "base": config["RAPIDAPI_BASE_URL"], "path": config["RAPIDAPI_SEARCH_PATH"],
                      "parameter": config["RAPIDAPI_QUERY_PARAMETER"]}
        def fetch():
            return StreamingAvailabilityService(api_client("RAPIDAPI"), config["RAPIDAPI_SEARCH_PATH"],
                config["RAPIDAPI_QUERY_PARAMETER"], country).search(query, media_type)
        return cached("streaming", parameters, fetch, config["API_CACHE_TTL_SECONDS"],
                      "https://docs.movieofthenight.com/")


class RandomMovie:
    def random(self, media_type="all", genre="all", *, refresh=False):
        config = current_app.config
        parameters = {"type": media_type.lower(), "genre": genre.casefold(),
                      "base": config["IMDB_API_BASE_URL"], "path": config["IMDB_RANDOM_PATH"]}
        return cached("imdb", parameters,
            lambda: ImdbService(api_client("IMDB_API"), config["IMDB_RANDOM_PATH"]).random(media_type, genre),
            config["IMDB_CACHE_TTL_SECONDS"], "https://rapidapi.com/", refresh=refresh)

    def random_title(self, media_type="all", genre="all", *, refresh=False):
        return self.random(media_type, genre, refresh=refresh)[0]["primaryTitle"]


class BoxOffice:
    SOURCE_URL = BoxOfficeService.SOURCE_URL

    def search(self, query=""):
        records = cached("box_office", {"url": self.SOURCE_URL}, BoxOfficeService()._fetch,
                         current_app.config["SCRAPE_CACHE_TTL_SECONDS"], self.SOURCE_URL)
        results = [item for item in records if query.casefold() in item["title"].casefold()]
        return {"results": results, "count": len(results), "source_url": self.SOURCE_URL,
                "fetched_at": g.cache_info["fetched_at"], "stale": g.cache_info["status"] == "stale"}
