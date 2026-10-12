"""Consistent safe failures across HTML and JSON endpoints."""
from flask import g, jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from services.cache_service import CacheBusy
from services.validation import ValidationError


def register_errors(app):
    def respond(message, status):
        if request.path.startswith("/api/"):
            return jsonify(error=message), status
        return render_template("error.html", message=message), status

    @app.errorhandler(ValidationError)
    def validation(error):
        return respond(str(error), 400)

    @app.errorhandler(CacheBusy)
    def cache_busy(error):
        response, status = respond(str(error), 503)
        return response, status, {"Retry-After": "60"}

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.warning("Database operation failed")
        return respond("Saved data is temporarily unavailable. Please try again later.", 503)

    @app.errorhandler(413)
    def oversized(error):
        return respond("The request body is too large.", 413)

    @app.after_request
    def cache_headers(response):
        if getattr(g, "cache_info", None):
            response.headers["X-Data-Cache"] = g.cache_info["status"]
            if g.cache_info["status"] == "stale":
                response.headers["Warning"] = '110 - "Response is stale"'
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
