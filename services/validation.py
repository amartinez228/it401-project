"""Validation at the HTTP boundary; errors never echo secret input."""
import math
from datetime import date
from urllib.parse import urlsplit


class ValidationError(ValueError):
    pass


def text(value, field, maximum, required=False):
    if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 and c not in '\n\t\r' for c in value):
        raise ValidationError(f"{field} must be text of at most {maximum} characters.")
    value = " ".join(value.split())
    if required and not value:
        raise ValidationError(f"{field} is required.")
    return value


def integer(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValidationError(f"{field} must be an integer.")
    try:
        result = int(value)
    except ValueError:
        raise ValidationError(f"{field} must be an integer.") from None
    if not minimum <= result <= maximum:
        raise ValidationError(f"{field} must be between {minimum} and {maximum}.")
    return result


def search_filters(args):
    query = text(args.get("q", ""), "q", 200)
    media_type = args.get("type", "all").lower()
    if media_type not in ("all", "movie", "show"):
        raise ValidationError("type must be all, Movie, or Show.")
    genre = text(args.get("genre", "all"), "genre", 80, True)
    try:
        rating = float(args.get("rating", "0"))
    except (ValueError, TypeError):
        raise ValidationError("rating must be a number between 0 and 5.") from None
    if not math.isfinite(rating) or not 0 <= rating <= 5:
        raise ValidationError("rating must be a number between 0 and 5.")
    year = args.get("year", "all")
    if year != "all":
        year = str(integer(year, "year", 1800, date.today().year + 10))
    return {"query": query, "media_type": {"movie": "Movie", "show": "Show"}.get(media_type, "all"),
            "genre": genre, "min_rating": str(args.get("rating", "0")), "year": year}


def record_input(payload, partial=False):
    if not isinstance(payload, dict) or not payload:
        raise ValidationError("Provide a non-empty JSON object.")
    allowed = {"title", "synopsis", "year", "media_type", "genres", "tags", "notes", "source_url"}
    if set(payload) - allowed:
        raise ValidationError("The request contains unsupported fields.")
    if not partial and "title" not in payload:
        raise ValidationError("title is required.")
    result = {}
    for field, value in payload.items():
        if field in ("genres", "tags"):
            if not isinstance(value, list) or len(value) > 20:
                raise ValidationError(f"{field} must be a list of at most 20 strings.")
            result[field] = list(dict.fromkeys(text(item, field, 80, True) for item in value))
        elif field == "year":
            result[field] = None if value is None else integer(value, field, 1800, date.today().year + 10)
        elif field == "media_type":
            if value not in ("Movie", "Show"):
                raise ValidationError("media_type must be Movie or Show.")
            result[field] = value
        elif field == "source_url":
            if value is None:
                result[field] = None
                continue
            value = text(value, field, 2048, True)
            try:
                url = urlsplit(value)
                valid = url.scheme == "https" and url.hostname and not url.username and not url.password
            except ValueError:
                valid = False
            if not valid:
                raise ValidationError("source_url must be an HTTPS URL without credentials.")
            result[field] = value
        else:
            result[field] = text(value, field, 300 if field == "title" else 10000, field == "title")
    return result
