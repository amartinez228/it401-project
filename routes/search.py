"""Search HTTP boundary; acquisition remains in the existing discovery routes."""
from flask import Blueprint, current_app, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from routes.records import find_record
from services.retrieval import SOURCES, SORTS, SearchOptions, parse_options, record_search, retrieve
from services.validation import ValidationError

search = Blueprint("search", __name__)


@search.get("/search")
def index():
    options = SearchOptions()
    data, message, status = None, None, 200
    try:
        options = parse_options(request.args)
        if options.q:
            data = retrieve(options)
            record_search(options, data["count"])
    except ValidationError as error:
        message, status = str(error), 400
        options.q = request.args.get("q", "")[:200]
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning("Saved search failed")
        message, status = "Search is temporarily unavailable. Please try again later.", 503
    def page_url(page):
        return url_for("search.index", **options.parameters(page))
    return render_template("search.html", options=options, data=data, message=message,
                           sources=SOURCES, sorts=SORTS, page_url=page_url), status


@search.get("/library/<int:record_id>")
def detail(record_id):
    record = find_record(record_id)
    if record is None:
        return render_template("error.html", message="Record not found."), 404
    return render_template("record.html", item=record.to_dict())
