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
        if not isinstance(results, list):
            return []

        return [self._normalize(show, index) for index, show in enumerate(results)]

    def _normalize(self, show, index):
        raw_rating = show.get("rating") or 0
        rating = round(raw_rating / 20, 1)
        show_type = show.get("showType", "movie")
        genres = [
            genre.get("name", "") if isinstance(genre, dict) else str(genre)
            for genre in show.get("genres", [])
        ]
        genres = [genre for genre in genres if genre]
        creators = show.get("directors") or show.get("creators") or []
        creator = ", ".join(creators[:2]) if creators else "Unknown creator"
        year = show.get("releaseYear") or show.get("firstAirYear") or "Unknown"

        if show_type == "movie" and show.get("runtime"):
            runtime = f"{show['runtime']} min"
        elif show.get("seasonCount"):
            season_count = show["seasonCount"]
            runtime = f"{season_count} season{'s' if season_count != 1 else ''}"
        else:
            runtime = "Series"

        image_set = show.get("imageSet") or {}
        vertical_poster = image_set.get("verticalPoster") or {}
        poster_url = next(
            (vertical_poster.get(size) for size in ("w480", "w360", "w600", "w240") if vertical_poster.get(size)),
            None,
        )

        streaming_options = []
        seen_options = set()
        for option in (show.get("streamingOptions") or {}).get(self.country, []):
            service = option.get("service") or {}
            service_name = service.get("name")
            option_type = option.get("type")
            link = option.get("link")
            identity = (service_name, option_type)
            if not service_name or not link or identity in seen_options:
                continue
            seen_options.add(identity)
            streaming_options.append({
                "service": service_name,
                "type": option_type or "watch",
                "link": link,
            })

        return {
            "id": show.get("id") or show.get("imdbId") or f"api-{index}",
            "title": show.get("title") or show.get("originalTitle") or "Untitled",
            "year": year,
            "type": "Movie" if show_type == "movie" else "Show",
            "genres": genres,
            "rating": rating,
            "match": int(raw_rating),
            "runtime": runtime,
            "creator": creator,
            "talent": (show.get("cast") or [])[:4],
            "topics": genres[:3],
            "synopsis": show.get("overview") or "No synopsis is available yet.",
            "art": self.ART_CLASSES[index % len(self.ART_CLASSES)],
            "poster_url": poster_url,
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
