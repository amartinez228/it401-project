import math
import hashlib
from urllib.parse import urlsplit


def safe_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password else None
    except ValueError:
        return None


def strings(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def mapping(value):
    return value if isinstance(value, dict) else {}


class StreamingAvailabilityService:
    """Translate Streaming Availability responses into BetterBoxd media cards."""

    ART_CLASSES = (
        "art-violet",
        "art-coral",
        "art-lime",
        "art-blue",
        "art-gold",
        "art-orange",
        "art-pink",
        "art-red",
    )

    def __init__(self, api_client, search_path, query_parameter="title", country="us"):
        self.api_client = api_client
        self.search_path = search_path
        self.query_parameter = query_parameter
        self.country = country

    def search(self, query, media_type="all"):
        params = {
            self.query_parameter: query,
        }
        if "country=" not in self.search_path:
            params["country"] = self.country
        show_type = {"movie": "movie", "show": "series"}.get(media_type.lower())
        if show_type:
            params["show_type"] = show_type

        results = self.api_client.get(self.search_path, params=params)
        if isinstance(results, dict) and isinstance(results.get("results"), list):
            results = results["results"]
        if not isinstance(results, list):
            raise ValueError("Unexpected movie response format.")
        valid = [show for show in results if isinstance(show, dict) and isinstance(show.get("title") or show.get("originalTitle"), str)]
        if results and not valid:
            raise ValueError("No usable movie records were returned.")
        return [self._normalize(show, index) for index, show in enumerate(valid)]

    def _normalize(self, show, index):
        try:
            raw_rating = float(show.get("rating") or 0)
            raw_rating = min(100, max(0, raw_rating)) if math.isfinite(raw_rating) else 0
        except (TypeError, ValueError):
            raw_rating = 0
        rating = round(raw_rating / 20, 1)
        show_type = show.get("showType", "movie")
        genres = [
            genre.get("name", "") if isinstance(genre, dict) else str(genre)
            for genre in (show.get("genres") if isinstance(show.get("genres"), list) else [])
        ]
        genres = [genre for genre in genres if isinstance(genre, str) and genre]
        creators = strings(show.get("directors")) or strings(show.get("creators"))
        creator = ", ".join(creators[:2]) if creators else "Unknown creator"
        year = show.get("releaseYear") or show.get("firstAirYear")
        year = year if type(year) is int and 1800 <= year <= 9999 else "Unknown"
        title = (show.get("title") or show.get("originalTitle") or "Untitled").strip()[:300] or "Untitled"
        provider_id = show.get("id") or show.get("imdbId")
        if not isinstance(provider_id, str) or not provider_id:
            provider_id = "derived-" + hashlib.sha256(f"{title.casefold()}|{year}|{show_type}".encode()).hexdigest()

        if show_type == "movie" and show.get("runtime"):
            runtime = f"{show['runtime']} min"
        elif show.get("seasonCount"):
            season_count = show["seasonCount"]
            runtime = f"{season_count} season{'s' if season_count != 1 else ''}"
        else:
            runtime = "Series"

        image_set = mapping(show.get("imageSet"))
        vertical_poster = mapping(image_set.get("verticalPoster"))
        poster_url = next(
            (vertical_poster.get(size) for size in ("w480", "w360", "w600", "w240") if vertical_poster.get(size)),
            None,
        )

        streaming_options = []
        seen_options = set()
        options = mapping(show.get("streamingOptions")).get(self.country)
        for option in options if isinstance(options, list) else []:
            if not isinstance(option, dict):
                continue
            service = mapping(option.get("service"))
            service_name = service.get("name")
            option_type = option.get("type")
            link = safe_url(option.get("link"))
            identity = (service_name, option_type)
            if not isinstance(service_name, str) or not isinstance(option_type, (str, type(None))) or not link or identity in seen_options:
                continue
            seen_options.add(identity)
            streaming_options.append({
                "service": service_name,
                "type": option_type or "watch",
                "link": link,
            })

        return {
            "id": provider_id,
            "title": title,
            "year": year,
            "type": "Movie" if show_type == "movie" else "Show",
            "genres": genres,
            "rating": rating,
            "match": int(raw_rating),
            "runtime": runtime,
            "creator": creator,
            "talent": strings(show.get("cast"))[:4],
            "topics": genres[:3],
            "synopsis": show["overview"][:10000] if isinstance(show.get("overview"), str) else "No synopsis is available yet.",
            "art": self.ART_CLASSES[index % len(self.ART_CLASSES)],
            "poster_url": safe_url(poster_url),
            "streaming_options": streaming_options,
            "source": "rapidapi",
        }

    @staticmethod
    def apply_filters(titles, genre="all", min_rating=0, year="all"):
        try:
            min_rating = float(min_rating)
        except (TypeError, ValueError):
            min_rating = 0

        filtered = []
        for title in titles:
            title_genres = [item.lower() for item in title.get("genres", [])]
            if genre.lower() != "all" and genre.lower() not in title_genres:
                continue
            if year != "all" and str(title.get("year")) != str(year):
                continue
            if title.get("rating", 0) < min_rating:
                continue
            filtered.append(title)

        return filtered
