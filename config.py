import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///betterboxd.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 1800}
    MAX_CONTENT_LENGTH = 64 * 1024
    ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN")
    API_CACHE_TTL_SECONDS = int(os.environ.get("API_CACHE_TTL_SECONDS", "86400"))
    IMDB_CACHE_TTL_SECONDS = int(os.environ.get("IMDB_CACHE_TTL_SECONDS", "900"))
    SCRAPE_CACHE_TTL_SECONDS = int(os.environ.get("SCRAPE_CACHE_TTL_SECONDS", "3600"))
    CACHE_MAX_STALE_SECONDS = int(os.environ.get("CACHE_MAX_STALE_SECONDS", "604800"))
    DATA_DIR = os.path.join(BASE_DIR, "data")

    # Application owner's credentials, shared by all visitors through Flask.
    # Set on the server via environment variables or a Git-ignored .env file.
    RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
    RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST")
    RAPIDAPI_BASE_URL = os.environ.get("RAPIDAPI_BASE_URL")
    RAPIDAPI_SEARCH_PATH = os.environ.get("RAPIDAPI_SEARCH_PATH", "/shows/search/title")
    RAPIDAPI_QUERY_PARAMETER = os.environ.get("RAPIDAPI_QUERY_PARAMETER", "title")
    RAPIDAPI_COUNTRY = os.environ.get("RAPIDAPI_COUNTRY", "us")

    # IMDb236 uses the same RapidAPI app key with a different host.
    IMDB_API_KEY = os.environ.get("IMDB_API_KEY") or RAPIDAPI_KEY
    IMDB_API_HOST = os.environ.get("IMDB_API_HOST", "imdb236.p.rapidapi.com")
    IMDB_API_BASE_URL = os.environ.get(
        "IMDB_API_BASE_URL",
        "https://imdb236.p.rapidapi.com",
    )
    IMDB_RANDOM_PATH = os.environ.get("IMDB_RANDOM_PATH", "/api/imdb/random")

    # Optional key reserved for a future AI integration.
    AI_SERVICE_API_KEY = os.environ.get("AI_SERVICE_API_KEY")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    ADMIN_API_TOKEN = "test-owner-token"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
