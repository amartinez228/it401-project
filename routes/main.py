import requests

from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for

from services.api_service import RapidApiService
from services.search_service import SearchService


def register_routes(app):
    media_catalog = SearchService(app.config["DATA_DIR"])

    @app.route("/")
    def index():
        featured = media_catalog.search(min_rating=4.4, limit=4)
        return render_template("index.html", featured=featured)

    @app.route("/explore")
    def explore():
        filters = {
            "query": request.args.get("q", ""),
            "media_type": request.args.get("type", "all"),
            "genre": request.args.get("genre", "all"),
            "min_rating": request.args.get("rating", "0"),
            "year": request.args.get("year", "all"),
        }
        titles = media_catalog.search(**filters)
        return render_template(
            "explore.html",
            titles=titles,
            genres=media_catalog.genres(),
            years=media_catalog.years(),
            filters=filters,
        )

    @app.route("/signin", methods=["GET", "POST"])
    def signin():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")

            if not email or "@" not in email or not password:
                flash("Enter a valid email and password to continue.", "error")
                return render_template("signin.html", email=email), 400

            session["user_name"] = email.split("@", 1)[0].replace(".", " ").title()
            flash("Welcome back. Your next great watch is waiting.", "success")
            return redirect(url_for("explore"))

        return render_template("signin.html")

    @app.post("/signout")
    def signout():
        session.pop("user_name", None)
        flash("You have been signed out.", "success")
        return redirect(url_for("index"))

    @app.route("/api/media")
    def media_api():
        """JSON endpoint that uses the same filters as the Explore page."""
        titles = media_catalog.search(
            query=request.args.get("q", ""),
            media_type=request.args.get("type", "all"),
            genre=request.args.get("genre", "all"),
            min_rating=request.args.get("rating", "0"),
            year=request.args.get("year", "all"),
        )
        return jsonify({"count": len(titles), "results": titles})

    @app.get("/api/rapid/search")
    def rapid_api_search():
        """Search the configured RapidAPI provider without exposing its key."""
        required_settings = (
            "RAPIDAPI_KEY",
            "RAPIDAPI_HOST",
            "RAPIDAPI_BASE_URL",
        )
        missing = [name for name in required_settings if not current_app.config.get(name)]
        if missing:
            return jsonify({
                "error": "RapidAPI is not configured.",
                "missing": missing,
            }), 503

        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"error": "Add a non-empty q query parameter."}), 400

        service = RapidApiService(
            base_url=current_app.config["RAPIDAPI_BASE_URL"],
            api_key=current_app.config["RAPIDAPI_KEY"],
            host=current_app.config["RAPIDAPI_HOST"],
        )
        params = {current_app.config["RAPIDAPI_QUERY_PARAMETER"]: query}

        try:
            result = service.get(current_app.config["RAPIDAPI_SEARCH_PATH"], params=params)
        except requests.Timeout:
            return jsonify({"error": "The external API timed out. Try again."}), 504
        except (requests.RequestException, ValueError):
            current_app.logger.exception("RapidAPI request failed")
            return jsonify({"error": "The external API request failed."}), 502

        return jsonify(result)
