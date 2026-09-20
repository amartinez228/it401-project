import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev"
    DATA_DIR = os.path.join(BASE_DIR, "data")

    # RapidAPI settings. Secrets stay in the local .env file.
    RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
    RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST")
    RAPIDAPI_BASE_URL = os.environ.get("RAPIDAPI_BASE_URL")
    RAPIDAPI_SEARCH_PATH = os.environ.get("RAPIDAPI_SEARCH_PATH", "/search")
    RAPIDAPI_QUERY_PARAMETER = os.environ.get("RAPIDAPI_QUERY_PARAMETER", "query")

    # Optional key reserved for a future AI integration.
    AI_SERVICE_API_KEY = os.environ.get("AI_SERVICE_API_KEY")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
