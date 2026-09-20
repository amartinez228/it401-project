import requests

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.api_service import RapidApiService
from services.imdb_service import ImdbService
from services.search_service import SearchService
from services.streaming_service import StreamingAvailabilityService


def register_routes(app):
    media_catalog = SearchService(app.config["DATA_DIR"])

    def rapid_api_is_configured():
        return all(
            current_app.config.get(name)
            for name in ("RAPIDAPI_KEY", "RAPIDAPI_HOST", "RAPIDAPI_BASE_URL")
        )

    def streaming_service():
        api_client = RapidApiService(
            base_url=current_app.config["RAPIDAPI_BASE_URL"],
            api_key=current_app.config["RAPIDAPI_KEY"],
            host=current_app.config["RAPIDAPI_HOST"],
        )
        return StreamingAvailabilityService(
            api_client=api_client,
            search_path=current_app.config["RAPIDAPI_SEARCH_PATH"],
            query_parameter=current_app.config["RAPIDAPI_QUERY_PARAMETER"],
            country=current_app.config["RAPIDAPI_COUNTRY"],
        )

    def imdb_api_is_configured():
        return all(
            current_app.config.get(name)
            for name in ("IMDB_API_KEY", "IMDB_API_HOST", "IMDB_API_BASE_URL")
        )

    def imdb_service():
        api_client = RapidApiService(
            base_url=current_app.config["IMDB_API_BASE_URL"],
            api_key=current_app.config["IMDB_API_KEY"],
            host=current_app.config["IMDB_API_HOST"],
        )
        return ImdbService(
            api_client=api_client,
            random_path=current_app.config["IMDB_RANDOM_PATH"],
        )

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

        if request.args.get("action") == "surprise":
            if not imdb_api_is_configured():
                flash("The IMDb surprise service is not configured yet.", "error")
                return redirect(url_for("explore"))
            try:
                surprise_title = imdb_service().random_title(
                    media_type=filters["media_type"],
                    genre=filters["genre"],
                )
            except requests.HTTPError as error:
                current_app.logger.exception("IMDb random-title request failed")
                if error.response is not None and error.response.status_code == 403:
                    message = "Subscribe to the IMDb236 API in RapidAPI before using Surprise me."
                else:
                    message = "IMDb couldn't choose a title right now. Please try again."
                flash(message, "error")
                return redirect(url_for("explore"))
            except (requests.RequestException, ValueError):
                current_app.logger.exception("IMDb random-title request failed")
                flash("IMDb couldn't choose a title right now. Please try again.", "error")
                return redirect(url_for("explore"))

            flash(f"Your IMDb surprise pick is {surprise_title}.", "success")
            redirect_filters = {"q": surprise_title}
            if filters["media_type"] != "all":
                redirect_filters["type"] = filters["media_type"]
            return redirect(url_for("explore", **redirect_filters))

        api_error = None
        using_external_api = bool(filters["query"] and rapid_api_is_configured())

        if using_external_api:
            try:
                titles = streaming_service().search(
                    filters["query"],
                    media_type=filters["media_type"],
                )
                titles = StreamingAvailabilityService.apply_filters(
                    titles,
                    genre=filters["genre"],
                    min_rating=filters["min_rating"],
                    year=filters["year"],
                )
            except requests.Timeout:
                titles = []
                api_error = "The movie service timed out. Please try your search again."
            except (requests.RequestException, ValueError):
                current_app.logger.exception("Streaming Availability search failed")
                titles = []
                api_error = "Live movie search is temporarily unavailable. Please try again."
        else:
            titles = media_catalog.search(**filters)

        genres = set(media_catalog.genres())
        years = set(media_catalog.years())
        for title in titles:
            genres.update(title.get("genres", []))
            if isinstance(title.get("year"), int):
                years.add(title["year"])

        return render_template(
            "explore.html",
            titles=titles,
            genres=sorted(genres),
            years=sorted(years, reverse=True),
            filters=filters,
            api_error=api_error,
            using_external_api=using_external_api,
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
        params = {
            current_app.config["RAPIDAPI_QUERY_PARAMETER"]: query,
        }
        if "country=" not in current_app.config["RAPIDAPI_SEARCH_PATH"]:
            params["country"] = current_app.config["RAPIDAPI_COUNTRY"]
        media_type = request.args.get("type", "all").lower()
        show_type = {"movie": "movie", "show": "series"}.get(media_type)
        if show_type:
            params["show_type"] = show_type

        try:
            result = service.get(current_app.config["RAPIDAPI_SEARCH_PATH"], params=params)
        except requests.Timeout:
            return jsonify({"error": "The external API timed out. Try again."}), 504
        except (requests.RequestException, ValueError):
            current_app.logger.exception("RapidAPI request failed")
            return jsonify({"error": "The external API request failed."}), 502

        return jsonify(result)

    @app.get("/api/imdb/random")
    def imdb_random_api():
        """Return a random IMDb title without exposing the RapidAPI key."""
        required_settings = ("IMDB_API_KEY", "IMDB_API_HOST", "IMDB_API_BASE_URL")
        missing = [name for name in required_settings if not current_app.config.get(name)]
        if missing:
            return jsonify({
                "error": "IMDb236 is not configured.",
                "missing": missing,
            }), 503

        try:
            result = imdb_service().random(
                media_type=request.args.get("type", "all"),
                genre=request.args.get("genre", "all"),
            )
        except requests.Timeout:
            return jsonify({"error": "The IMDb API timed out. Try again."}), 504
        except requests.HTTPError as error:
            current_app.logger.exception("IMDb API request failed")
            upstream_status = error.response.status_code if error.response is not None else None
            message = "The IMDb API rejected the request."
            if upstream_status == 403:
                message = "The RapidAPI app is not subscribed to IMDb236."
            return jsonify({
                "error": message,
                "upstream_status": upstream_status,
            }), 502
        except (requests.RequestException, ValueError):
            current_app.logger.exception("IMDb API request failed")
            return jsonify({"error": "The IMDb API request failed."}), 502

        return jsonify(result)
