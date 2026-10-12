class ImdbService:
    """Client helpers for the IMDb236 random-title endpoint."""

    TYPE_MAP = {
        "movie": "movie",
        "show": "tvSeries",
    }
    GENRE_MAP = {
        "Science Fiction": "Sci-Fi",
    }

    def __init__(self, api_client, random_path="/api/imdb/random"):
        self.api_client = api_client
        self.random_path = random_path

    def random(self, media_type="all", genre="all"):
        params = {}
        api_type = self.TYPE_MAP.get(media_type.lower())
        if api_type:
            params["type"] = api_type
        if genre.lower() != "all":
            params["genre"] = self.GENRE_MAP.get(genre, genre)
        payload = self.api_client.get(self.random_path, params=params)
        item = self._first_title(payload)
        title = item.get("primaryTitle") or item.get("originalTitle") or item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("IMDb returned a response without a title.")
        return [{"primaryTitle": title.strip()}]

    def random_title(self, media_type="all", genre="all"):
        payload = self.random(media_type=media_type, genre=genre)
        item = self._first_title(payload)
        title = item.get("primaryTitle") or item.get("originalTitle") or item.get("title")
        if not title:
            raise ValueError("IMDb returned a response without a title.")
        return title

    @staticmethod
    def _first_title(payload):
        if isinstance(payload, list):
            return payload[0] if payload and isinstance(payload[0], dict) else {}
        if not isinstance(payload, dict):
            return {}

        for field in ("results", "titles", "items"):
            items = payload.get(field)
            if isinstance(items, list) and items and isinstance(items[0], dict):
                return items[0]

        result = payload.get("result")
        if isinstance(result, dict):
            return result
        return payload
