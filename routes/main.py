from flask import flash, jsonify, redirect, render_template, request, session, url_for

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
