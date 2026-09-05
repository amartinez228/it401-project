import json
from pathlib import Path


class SearchService:
    """Loads and filters the local BetterBoxd media catalog."""

    def __init__(self, data_dir):
        self.data_file = Path(data_dir) / "media.json"

    def all_media(self):
        """Return all titles from the JSON catalog."""
        try:
            with self.data_file.open(encoding="utf-8") as media_file:
                data = json.load(media_file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

        return data if isinstance(data, list) else []

    def search(
        self,
        query="",
        media_type="all",
        genre="all",
        min_rating=0,
        year="all",
        limit=None,
    ):
        """Filter titles using the values supplied by the Explore page."""
        query = query.strip().lower()
        media_type = media_type.lower()
        genre = genre.lower()

        try:
            min_rating = float(min_rating)
        except (TypeError, ValueError):
            min_rating = 0

        results = []
        for item in self.all_media():
            searchable_text = " ".join(
                [
                    item.get("title", ""),
                    item.get("creator", ""),
                    item.get("synopsis", ""),
                    *item.get("genres", []),
                    *item.get("talent", []),
                    *item.get("topics", []),
                ]
            ).lower()

            if query and query not in searchable_text:
                continue
            if media_type != "all" and item.get("type", "").lower() != media_type:
                continue
            if genre != "all" and genre not in [g.lower() for g in item.get("genres", [])]:
                continue
            if year != "all" and str(item.get("year")) != str(year):
                continue
            if float(item.get("rating", 0)) < min_rating:
                continue

            results.append(item)

        results.sort(key=lambda item: (item.get("match", 0), item.get("rating", 0)), reverse=True)
        return results[:limit] if limit else results

    def genres(self):
        return sorted({genre for item in self.all_media() for genre in item.get("genres", [])})

    def years(self):
        return sorted({item.get("year") for item in self.all_media()}, reverse=True)
