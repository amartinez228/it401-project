"""Validated library API; mutations require the owner's server-managed token."""
from functools import wraps
from hmac import compare_digest

from flask import Blueprint, current_app, jsonify, render_template, request, url_for
from sqlalchemy import select

from extensions import db
from models import Record
from services.record_service import create_record, delete_record, list_records, update_record
from services.validation import ValidationError, integer, record_input, text

records = Blueprint("records", __name__)


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = current_app.config.get("ADMIN_API_TOKEN")
        if not expected:
            return jsonify(error="Library editing is not configured."), 503
        provided = request.headers.get("Authorization", "")
        if not compare_digest(provided.encode(), f"Bearer {expected}".encode()):
            return jsonify(error="An owner token is required."), 401
        return view(*args, **kwargs)
    return wrapped


def body(partial=False):
    if not request.is_json:
        raise ValidationError("Send an application/json request body.")
    return record_input(request.get_json(silent=True), partial=partial)


def find_record(record_id):
    return db.session.scalar(select(Record).where(Record.id == record_id, Record.deleted_at.is_(None)))


def search():
    query = text(request.args.get("q", ""), "q", 200)
    source = request.args.get("source") or None
    if source not in (None, "manual", "streaming", "imdb", "box_office"):
        raise ValidationError("Unknown source.")
    page = integer(request.args.get("page", "1"), "page", 1, 10000)
    limit = integer(request.args.get("limit", "20"), "limit", 1, 100)
    return list_records(query, source, page, limit)


@records.get("/library")
def library():
    return render_template("library.html", data=search(), query=request.args.get("q", ""))


@records.get("/api/records")
def index():
    return jsonify(search())


@records.get("/api/records/<int:record_id>")
def detail(record_id):
    record = find_record(record_id)
    return (jsonify(record.to_dict()), 200) if record else (jsonify(error="Record not found."), 404)


@records.post("/api/records")
@owner_required
def create():
    record = create_record(body())
    return jsonify(record.to_dict()), 201, {"Location": url_for("records.detail", record_id=record.id)}


@records.patch("/api/records/<int:record_id>")
@owner_required
def update(record_id):
    record = find_record(record_id)
    if record is None:
        return jsonify(error="Record not found."), 404
    return jsonify(update_record(record, body(partial=True)).to_dict())


@records.delete("/api/records/<int:record_id>")
@owner_required
def delete(record_id):
    record = find_record(record_id)
    if record is None:
        return jsonify(error="Record not found."), 404
    delete_record(record)
    return "", 204
