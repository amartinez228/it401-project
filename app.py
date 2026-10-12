import os

from flask import Flask

from config import BASE_DIR, config
from routes.main import register_routes
from routes.records import records
from routes.errors import register_errors
from extensions import db, migrate
import models  # Register tables with SQLAlchemy before migrations run.


def create_app(config_name=None, overrides=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "default")

    # IDE script launches and Flask CLI imports must share one instance directory.
    # Flask otherwise resolves __main__ relative to the launch working directory.
    app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
    app.config.from_object(config[config_name])

    if overrides:
        app.config.update(overrides)
    if config_name == "production":
        if not os.environ.get("DATABASE_URL") and not (overrides or {}).get("SQLALCHEMY_DATABASE_URI"):
            raise RuntimeError("Set DATABASE_URL before starting production.")
        if app.config["SECRET_KEY"] == "dev":
            raise RuntimeError("Set a private SECRET_KEY before starting production.")
    for name in ("API_CACHE_TTL_SECONDS", "IMDB_CACHE_TTL_SECONDS", "SCRAPE_CACHE_TTL_SECONDS", "CACHE_MAX_STALE_SECONDS"):
        if app.config[name] <= 0:
            raise ValueError(f"{name} must be positive.")
    db.init_app(app)
    migrate.init_app(app, db)
    register_errors(app)
    app.register_blueprint(records)
    register_routes(app)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=app.config.get("DEBUG", False))
